"""Write paths: bulk issuance, revocation, notification resend.

Bulk issuance is a single transaction (plan D5). The idempotency record is written inside that same
transaction, so a crash either leaves both the certificates and the record, or neither.
"""

from __future__ import annotations

import json
import sqlite3

from ..errors import ApiError, not_found
from ..timezones import local_date, local_year, to_iso, utc_now
from . import repo
from .notify import notifier

MAX_BATCH = 1000


def _next_serial(conn: sqlite3.Connection, tenant_code: str, issued_at: str, tz: str) -> str:
    year = local_year(issued_at, tz)
    conn.execute(
        "insert into serial_counter (year, next_value) values (?, 0) on conflict(year) do nothing",
        (year,),
    )
    row = conn.execute(
        "update serial_counter set next_value = next_value + 1 where year = ? returning next_value",
        (year,),
    ).fetchone()
    return f"CERT-{tenant_code}-{year}-{row[0]:06d}"


def bulk_issue(
    conn: sqlite3.Connection,
    *,
    tenant_code: str,
    timezone: str,
    actor_id: str,
    actor_name: str,
    course_id: str,
    idempotency_key: str,
) -> dict:
    key = idempotency_key.strip()
    if not key:
        raise ApiError("invalid_request", "An idempotency key is required.", 422)

    issued_certificates: list[tuple[str, str | None]] = []

    conn.execute("begin immediate")
    try:
        replay = conn.execute(
            "select response_json from idempotency_record where key = ?", (key,)
        ).fetchone()
        if replay is not None:
            payload = json.loads(replay["response_json"])
            payload["replay"] = True
            conn.execute("commit")
            return payload

        course = conn.execute("select id, code, title from course where id = ?", (course_id,)).fetchone()
        if course is None:
            raise not_found("Course")

        candidates = conn.execute(
            """
            select e.learner_id, l.name as learner_name, l.email as learner_email,
                   c.id as certificate_id
            from enrollment e
            join learner l on l.id = e.learner_id
            left join certificate c
                   on c.course_id = e.course_id and c.learner_id = e.learner_id
            where e.course_id = ? and e.completed_at is not null
            order by l.name collate nocase
            """,
            (course_id,),
        ).fetchall()

        if len(candidates) > MAX_BATCH:
            raise ApiError(
                "batch_too_large",
                f"This course has {len(candidates)} completed learners; the limit per request is {MAX_BATCH}.",
                422,
            )

        rows: list[dict] = []
        counts = {"issued": 0, "skipped": 0, "failed": 0}
        issued_at = to_iso(utc_now())

        for candidate in candidates:
            if candidate["certificate_id"]:
                counts["skipped"] += 1
                rows.append(
                    {
                        "learnerId": candidate["learner_id"],
                        "learnerName": candidate["learner_name"],
                        "outcome": "skipped",
                        "reason": "Certificate already issued.",
                        "serial": None,
                    }
                )
                continue

            # One savepoint per candidate: the certificate, its serial allocation and its audit
            # row must land together or not at all. Without this, a failing audit insert leaves a
            # committed certificate with no audit trail (review P1).
            conn.execute("savepoint candidate")
            try:
                serial = _next_serial(conn, tenant_code, issued_at, timezone)
                certificate_id = f"crt_{serial.rsplit('-', 1)[1]}_{candidate['learner_id']}"
                conn.execute(
                    """
                    insert into certificate (id, course_id, learner_id, serial, issued_at,
                                             issued_local_date, issued_by, status,
                                             notification_status, notification_sent_at)
                    values (?, ?, ?, ?, ?, ?, ?, 'valid', 'pending', null)
                    """,
                    (
                        certificate_id,
                        course_id,
                        candidate["learner_id"],
                        serial,
                        issued_at,
                        local_date(issued_at, timezone),
                        actor_name,
                    ),
                )
                conn.execute(
                    """
                    insert into audit_entry (id, certificate_id, action, actor_user_id, at, detail)
                    values (?, ?, 'issued', ?, ?, ?)
                    """,
                    (
                        f"a_{certificate_id}_issued",
                        certificate_id,
                        actor_id,
                        issued_at,
                        f"Issued to {candidate['learner_name']} <{candidate['learner_email'] or 'no email'}> "
                        f"for {course['title']} ({serial}).",
                    ),
                )
                conn.execute("release candidate")
                issued_certificates.append((certificate_id, candidate["learner_email"]))
                counts["issued"] += 1
                rows.append(
                    {
                        "learnerId": candidate["learner_id"],
                        "learnerName": candidate["learner_name"],
                        "outcome": "issued",
                        "reason": serial,
                        "serial": serial,
                    }
                )
            except sqlite3.IntegrityError as exc:
                conn.execute("rollback to candidate")
                conn.execute("release candidate")
                # A duplicate means someone else certified this learner; anything else is a real
                # row failure and must be reported as `failed`, not hidden as a skip.
                already = conn.execute(
                    "select 1 from certificate where course_id = ? and learner_id = ?",
                    (course_id, candidate["learner_id"]),
                ).fetchone()
                if already is not None:
                    counts["skipped"] += 1
                    rows.append(
                        {
                            "learnerId": candidate["learner_id"],
                            "learnerName": candidate["learner_name"],
                            "outcome": "skipped",
                            "reason": "Certificate already issued.",
                            "serial": None,
                        }
                    )
                else:
                    counts["failed"] += 1
                    rows.append(
                        {
                            "learnerId": candidate["learner_id"],
                            "learnerName": candidate["learner_name"],
                            "outcome": "failed",
                            "reason": str(exc),
                            "serial": None,
                        }
                    )
            except sqlite3.Error as exc:  # pragma: no cover - defensive
                conn.execute("rollback to candidate")
                conn.execute("release candidate")
                counts["failed"] += 1
                rows.append(
                    {
                        "learnerId": candidate["learner_id"],
                        "learnerName": candidate["learner_name"],
                        "outcome": "failed",
                        "reason": str(exc),
                        "serial": None,
                    }
                )

        payload = {
            "courseId": course_id,
            "courseTitle": course["title"],
            "replay": False,
            "issuedAt": issued_at,
            "summary": counts,
            "rows": rows,
        }
        conn.execute(
            "insert into idempotency_record (key, course_id, status_code, response_json, created_at) values (?, ?, ?, ?, ?)",
            (key, course_id, 200, json.dumps(payload), issued_at),
        )
        conn.execute("commit")
    except Exception:
        conn.execute("rollback")
        raise

    # Delivery happens after commit, outside the write transaction (D8).
    _dispatch(conn, issued_certificates)
    return payload


def _dispatch(conn: sqlite3.Connection, issued: list[tuple[str, str | None]]) -> None:
    if not issued:
        return
    now = to_iso(utc_now())
    for certificate_id, email in issued:
        status = notifier.deliver(email=email)
        conn.execute(
            "update certificate set notification_status = ?, notification_sent_at = ? where id = ?",
            (status, now if status == "sent" else None, certificate_id),
        )
    conn.commit()


def revoke(conn: sqlite3.Connection, *, certificate_id: str, actor_id: str, actor_name: str, reason: str) -> None:
    reason = reason.strip()
    if len(reason) < 5:
        raise ApiError("invalid_reason", "A revocation reason of at least 5 characters is required.", 422)

    conn.execute("begin immediate")
    try:
        current = conn.execute(
            "select status from certificate where id = ?", (certificate_id,)
        ).fetchone()
        if current is None:
            raise not_found("Certificate")
        if current["status"] == "revoked":
            raise ApiError("already_revoked", "This certificate is already revoked.", 409)

        at = to_iso(utc_now())
        conn.execute(
            """
            update certificate
               set status = 'revoked', revoked_at = ?, revoked_by = ?, revoke_reason = ?
             where id = ?
            """,
            (at, actor_name, reason, certificate_id),
        )
        conn.execute(
            """
            insert into audit_entry (id, certificate_id, action, actor_user_id, at, detail)
            values (?, ?, 'revoked', ?, ?, ?)
            """,
            (f"a_{certificate_id}_revoked_{at}", certificate_id, actor_id, at, reason),
        )
        conn.execute("commit")
    except Exception:
        conn.execute("rollback")
        raise


def resend_notification(conn: sqlite3.Connection, *, certificate_id: str, actor_id: str) -> dict:
    row = conn.execute(
        """
        select c.id, c.serial, l.email
        from certificate c join learner l on l.id = c.learner_id
        where c.id = ?
        """,
        (certificate_id,),
    ).fetchone()
    if row is None:
        raise not_found("Certificate")
    if not row["email"]:
        raise ApiError("no_destination", "This learner has no email address on file.", 409)

    at = to_iso(utc_now())
    conn.execute("begin immediate")
    try:
        conn.execute(
            "update certificate set notification_status = 'sent', notification_sent_at = ? where id = ?",
            (at, certificate_id),
        )
        conn.execute(
            """
            insert into audit_entry (id, certificate_id, action, actor_user_id, at, detail)
            values (?, ?, 'notified', ?, ?, ?)
            """,
            (f"a_{certificate_id}_notified_{at}", certificate_id, actor_id, at, "Notification re-sent to the learner."),
        )
        conn.execute("commit")
    except Exception:
        conn.execute("rollback")
        raise

    return {"id": certificate_id, "notificationStatus": "sent", "notificationSentAt": at}
