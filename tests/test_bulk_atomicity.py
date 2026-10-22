"""Regression test for review P1: issuance and audit must be atomic per learner.

The original bug: a certificate was inserted, then its audit row failed, and the IntegrityError was
mistaken for "already issued" — so the batch committed certificates with no audit trail. The fix wraps
each candidate in a savepoint that rolls back the certificate and the serial allocation together.

The trigger here is the same technique the reviewer used: make audit inserts fail and check that no
certificate survives.
"""

from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

import pytest

from app.certs.service import bulk_issue
from app.seed import seed

FAR_330 = "c_acm_3"


@pytest.fixture()
def tenant_db(tmp_path: Path) -> sqlite3.Connection:
    base = tmp_path / "data"
    seed(base)
    conn = sqlite3.connect(base / "tenants" / "acm.db")
    conn.row_factory = sqlite3.Row
    conn.isolation_level = None
    conn.execute("PRAGMA foreign_keys=ON")
    yield conn
    conn.close()


def _counts(conn: sqlite3.Connection) -> tuple[int, int]:
    certificates = conn.execute("select count(*) from certificate").fetchone()[0]
    audits = conn.execute("select count(*) from audit_entry where action = 'issued'").fetchone()[0]
    return certificates, audits


def test_audit_failure_rolls_back_the_certificate(tenant_db: sqlite3.Connection) -> None:
    before = _counts(tenant_db)
    tenant_db.execute(
        "create trigger review_injected_audit_failure before insert on audit_entry "
        "begin select raise(abort, 'review injected audit failure'); end"
    )

    result = bulk_issue(
        tenant_db,
        tenant_code="ACM",
        timezone="Australia/Sydney",
        actor_id="u_t_acme",
        actor_name="Dana Whitfield",
        course_id=FAR_330,
        idempotency_key="review-p1-atomicity",
    )

    after = _counts(tenant_db)
    assert after[0] == before[0], "certificates were committed without their audit rows"
    assert after[1] == before[1], "audit rows leaked despite the failure"
    assert result["summary"]["issued"] == 0
    assert result["summary"]["failed"] == len(result["rows"])
    assert result["summary"]["skipped"] == 0
    assert all(row["outcome"] == "failed" for row in result["rows"])


def test_serial_counter_is_not_consumed_by_a_failed_row(tenant_db: sqlite3.Connection) -> None:
    def peak() -> int:
        row = tenant_db.execute("select coalesce(max(next_value), 0) from serial_counter").fetchone()
        return int(row[0])

    before = peak()
    tenant_db.execute(
        "create trigger review_injected_audit_failure before insert on audit_entry "
        "begin select raise(abort, 'review injected audit failure'); end"
    )
    bulk_issue(
        tenant_db,
        tenant_code="ACM",
        timezone="Australia/Sydney",
        actor_id="u_t_acme",
        actor_name="Dana Whitfield",
        course_id=FAR_330,
        idempotency_key="review-p1-counter",
    )
    assert peak() == before, "failed rows burned serial numbers"


def test_duplicate_is_still_reported_as_skipped(tenant_db: sqlite3.Connection) -> None:
    first = bulk_issue(
        tenant_db,
        tenant_code="ACM",
        timezone="Australia/Sydney",
        actor_id="u_t_acme",
        actor_name="Dana Whitfield",
        course_id=FAR_330,
        idempotency_key="review-p1-first",
    )
    second = bulk_issue(
        tenant_db,
        tenant_code="ACM",
        timezone="Australia/Sydney",
        actor_id="u_t_acme",
        actor_name="Dana Whitfield",
        course_id=FAR_330,
        idempotency_key="review-p1-second",
    )
    assert first["summary"]["issued"] > 0
    assert second["summary"]["issued"] == 0
    assert second["summary"]["skipped"] == len(second["rows"])
    assert second["summary"]["failed"] == 0
