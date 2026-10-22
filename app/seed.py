"""Deterministic demo data.

Re-runnable: every run recreates the control database and every tenant database from scratch, so
the data is always the same for the same code. One learner deliberately has no email address; one
certificate is deliberately revoked; one course has nobody left to certify.
"""

from __future__ import annotations

import random
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .db import Databases
from .timezones import local_date, local_year, to_iso, zone_abbr


@dataclass(frozen=True)
class TenantSpec:
    id: str
    name: str
    code: str
    timezone: str
    learners: int
    courses: tuple[tuple[str, str], ...]


TENANTS: tuple[TenantSpec, ...] = (
    TenantSpec(
        "t_acme",
        "Acme Field Services",
        "ACM",
        "Australia/Sydney",
        120,
        (
            ("WHS-101", "Workplace Safety Induction"),
            ("CSE-204", "Confined Space Entry"),
            ("MH-110", "Manual Handling"),
            ("FAR-330", "First Aid Refresher"),
        ),
    ),
    TenantSpec(
        "t_northwind",
        "Northwind Logistics",
        "NWL",
        "Australia/Perth",
        70,
        (
            ("SAE-100", "Site Access Essentials"),
            ("FOR-220", "Forklift Operator Recertification"),
            ("HRP-140", "Hazard Reporting"),
        ),
    ),
    TenantSpec(
        "t_meridian",
        "Meridian Health Group",
        "MRH",
        "Asia/Singapore",
        45,
        (
            ("DPF-100", "Data Privacy Fundamentals"),
            ("FSW-210", "Fire Safety Warden"),
            ("ERG-120", "Ergonomics at Work"),
        ),
    ),
)

ADMIN_NAMES = {
    "t_acme": "Dana Whitfield",
    "t_northwind": "Marcus Bell",
    "t_meridian": "Wei Ling Tan",
}

FIRST = ["Priya", "Marcus", "Dana", "Liam", "Sofia", "Noah", "Ava", "Ethan", "Mia", "Lucas", "Chloe",
         "Aiden", "Ruby", "Owen", "Isla", "Felix", "Nadia", "Hugo", "Elena", "Tariq", "Grace", "Jonah"]
LAST = ["Nair", "Whitfield", "Okafor", "Chen", "Bell", "Nguyen", "Patel", "Smith", "Kowalski",
        "Ibrahim", "Rossi", "Haddad", "Fernandes", "Tan", "Murphy", "Novak", "Silva", "Ahmed",
        "Dubois", "Park", "Costa", "Walsh"]

DOMAIN = {"t_acme": "acmefield.example", "t_northwind": "northwindlog.example", "t_meridian": "meridianhealth.example"}

# Fraction of completed enrollments that already hold a certificate, by course position.
ISSUE_RATE = (1.0, 0.45, 0.60, 0.0)

NO_EMAIL_LEARNER_INDEX = 7


def _learner_name(tenant_index: int, i: int) -> str:
    return f"{FIRST[(i + tenant_index * 5) % len(FIRST)]} {LAST[(i * 3 + tenant_index * 7) % len(LAST)]}"


def _iso(base: datetime, days: int, hours: int) -> str:
    return to_iso((base + timedelta(days=days, hours=hours)).replace(tzinfo=timezone.utc))


def _insert_tenant(db: Databases, spec: TenantSpec, tenant_index: int) -> dict:
    conn = db.tenant(spec.code)
    rng = random.Random(1000 + tenant_index)
    started = datetime(2026, 1, 5, tzinfo=timezone.utc)

    learners: list[tuple[str, str, str | None]] = []
    for i in range(spec.learners):
        name = _learner_name(tenant_index, i)
        email: str | None = f"{name.replace(' ', '.').lower()}@{DOMAIN[spec.id]}"
        if tenant_index == 0 and i == NO_EMAIL_LEARNER_INDEX:
            email = None
        learners.append((f"l_{spec.code.lower()}_{i:04d}", name, email))

    conn.executemany("insert into learner (id, name, email) values (?, ?, ?)", learners)
    conn.executemany(
        "insert into course (id, code, title) values (?, ?, ?)",
        [(f"c_{spec.code.lower()}_{k}", code, title) for k, (code, title) in enumerate(spec.courses)],
    )

    enrollments: list[tuple[str, str, str, str | None]] = []
    pending_certs: list[dict] = []
    cert_seq = 0

    for i, (learner_id, learner_name, email) in enumerate(learners):
        # The learner without an email is only enrolled in the last course, which never auto-issues,
        # so they stay eligible for the demo and end up with a skipped notification.
        positions = [len(spec.courses) - 1] if email is None else sorted({(i + k) % len(spec.courses) for k in range(1 + i % 3)})
        for position in positions:
            course_id = f"c_{spec.code.lower()}_{position}"
            completed = rng.random() < 0.88
            completed_at = _iso(started, rng.randint(0, 270), rng.randint(0, 10)) if completed else None
            enrollments.append((f"e_{spec.code.lower()}_{i:04d}_{position}", course_id, learner_id, completed_at))
            if not completed:
                continue
            rate = ISSUE_RATE[position % len(ISSUE_RATE)]
            if rng.random() >= rate:
                continue
            issued_at = _iso(datetime.fromisoformat(completed_at.replace("Z", "+00:00")), rng.randint(1, 5), rng.randint(0, 6))
            cert_seq += 1
            pending_certs.append(
                {
                    "id": f"crt_{spec.code.lower()}_{cert_seq:05d}",
                    "course_id": course_id,
                    "learner_id": learner_id,
                    "learner_name": learner_name,
                    "learner_email": email,
                    "issued_at": issued_at,
                }
            )

    conn.executemany(
        "insert into enrollment (id, course_id, learner_id, completed_at) values (?, ?, ?, ?)",
        enrollments,
    )

    pending_certs.sort(key=lambda c: c["issued_at"])
    counters: dict[int, int] = {}
    certificates: list[tuple] = []
    audits: list[tuple] = []

    for cert in pending_certs:
        year = local_year(cert["issued_at"], spec.timezone)
        counters[year] = counters.get(year, 0) + 1
        serial = f"CERT-{spec.code}-{year}-{counters[year]:06d}"
        status = "valid"
        revoked_at = revoked_by = revoke_reason = None
        notified = "sent" if cert["learner_email"] else "skipped"
        certificates.append(
            (
                cert["id"],
                cert["course_id"],
                cert["learner_id"],
                serial,
                cert["issued_at"],
                local_date(cert["issued_at"], spec.timezone),
                ADMIN_NAMES[spec.id],
                status,
                notified,
                cert["issued_at"] if notified == "sent" else None,
                revoked_at,
                revoked_by,
                revoke_reason,
            )
        )
        audits.append(
            (
                f"a_{cert['id']}_issued",
                cert["id"],
                "issued",
                "u_" + spec.id,
                cert["issued_at"],
                f"Issued to {cert['learner_name']} for {dict((c, t) for c, t in spec.courses)[_course_code(spec, cert['course_id'])]} ({serial}).",
            )
        )

    # One revoked certificate, so the revoked path is demoable from a cold start.
    revoked_index = next(
        (idx for idx, cert in enumerate(pending_certs) if cert["course_id"].endswith("_2")),
        len(pending_certs) - 1,
    )
    if pending_certs:
        cert = pending_certs[revoked_index]
        revoked_at = "2026-09-02T04:15:00Z"
        revoked_by = ADMIN_NAMES[spec.id]
        revoke_reason = "Issued in error — duplicate enrolment."
        row = list(certificates[revoked_index])
        row[7] = "revoked"
        row[10] = revoked_at
        row[11] = revoked_by
        row[12] = revoke_reason
        certificates[revoked_index] = tuple(row)
        audits.append(
            (
                f"a_{cert['id']}_revoked",
                cert["id"],
                "revoked",
                "u_" + spec.id,
                revoked_at,
                revoke_reason,
            )
        )

    conn.executemany(
        """
        insert into certificate (id, course_id, learner_id, serial, issued_at, issued_local_date,
                                 issued_by, status, notification_status, notification_sent_at,
                                 revoked_at, revoked_by, revoke_reason)
        values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        certificates,
    )
    conn.executemany(
        "insert into audit_entry (id, certificate_id, action, actor_user_id, at, detail) values (?, ?, ?, ?, ?, ?)",
        audits,
    )
    conn.executemany(
        "insert into serial_counter (year, next_value) values (?, ?)",
        sorted(counters.items()),
    )
    conn.commit()
    conn.close()

    return {
        "tenant": spec,
        "learners": len(learners),
        "courses": len(spec.courses),
        "enrollments": len(enrollments),
        "certificates": len(certificates),
    }


def _course_code(spec: TenantSpec, course_id: str) -> str:
    position = int(course_id.rsplit("_", 1)[1])
    return spec.courses[position][0]


def seed(base_dir: str | Path, *, reset: bool = True) -> list[dict]:
    base = Path(base_dir).resolve()
    if reset and base.exists():
        # The data directory can be a Docker bind mount: never remove the mount
        # itself or unrelated files. Reset only the known demo database files.
        databases = [base / "control.db", *(base / "tenants" / f"{t.code.lower()}.db" for t in TENANTS)]
        for path in databases:
            for suffix in ("", "-wal", "-shm"):
                Path(str(path) + suffix).unlink(missing_ok=True)
    db = Databases(base)

    control = db.control()
    control.executemany(
        "insert into tenant (id, name, code, timezone, db_file) values (?, ?, ?, ?, ?)",
        [(t.id, t.name, t.code, t.timezone, f"{t.code.lower()}.db") for t in TENANTS],
    )
    users: list[tuple[str, str, str]] = []
    memberships: list[tuple[str, str, str]] = []
    for spec in TENANTS:
        users.append((f"u_{spec.id}", ADMIN_NAMES[spec.id], f"admin@{DOMAIN[spec.id]}"))
        memberships.append((f"u_{spec.id}", spec.id, "admin"))

    # A read-only account, to prove the viewer role is real.
    users.append(("u_viewer_acme", "Alex Chen", "alex.chen@acmefield.example"))
    memberships.append(("u_viewer_acme", "t_acme", "viewer"))

    control.executemany("insert into app_user (id, name, email) values (?, ?, ?)", users)
    control.executemany("insert into membership (user_id, tenant_id, role) values (?, ?, ?)", memberships)
    control.commit()
    control.close()

    summary = []
    for index, spec in enumerate(TENANTS):
        summary.append(_insert_tenant(db, spec, index))
    return summary


def main(argv: list[str]) -> int:
    base = argv[1] if len(argv) > 1 else str(Path(__file__).resolve().parent.parent / "data")
    for row in seed(base):
        tenant = row["tenant"]
        print(
            f"{tenant.name:<24} {row['certificates']:>5} certificates  "
            f"{row['enrollments']:>5} enrolments  tz={tenant.timezone} ({zone_abbr(tenant.timezone)})"
        )
    print(f"seeded into {Path(base).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
