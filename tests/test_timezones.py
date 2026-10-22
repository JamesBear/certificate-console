from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from app.certs.service import _next_serial
from app.seed import seed
from app.timezones import local_date, local_year, zone_label


def test_sydney_shifts_between_january_and_july() -> None:
    january = "2026-01-15T23:30:00Z"
    july = "2026-07-14T23:30:00Z"
    assert zone_label(january, "Australia/Sydney") == "AEDT · UTC+11"
    assert zone_label(july, "Australia/Sydney") == "AEST · UTC+10"
    # Same clock time in UTC, one hour apart locally.
    assert local_date(january, "Australia/Sydney") == "2026-01-16"
    assert local_date(july, "Australia/Sydney") == "2026-07-15"


def test_perth_never_shifts() -> None:
    january = "2026-01-15T23:30:00Z"
    july = "2026-07-14T23:30:00Z"
    assert zone_label(january, "Australia/Perth") == zone_label(july, "Australia/Perth")
    assert zone_label(january, "Australia/Perth") == "AWST · UTC+8"


def test_local_date_crosses_the_date_line_at_midnight_utc() -> None:
    # 23:30 UTC on the 31st is already New Year's Day in Sydney.
    assert local_date("2026-12-31T23:30:00Z", "Australia/Sydney") == "2027-01-01"
    assert local_year("2026-12-31T23:30:00Z", "Australia/Sydney") == 2027
    # ... but still the old year in UTC and in Perth.
    assert local_year("2026-12-31T23:30:00Z", "Australia/Perth") == 2027
    assert local_date("2026-12-31T10:00:00Z", "Australia/Sydney") == "2026-12-31"


def test_serial_uses_the_tenant_local_year(tmp_path: Path) -> None:
    base = tmp_path / "data"
    seed(base)
    conn = sqlite3.connect(base / "tenants" / "acm.db")
    conn.row_factory = sqlite3.Row
    try:
        serial = _next_serial(conn, "ACM", "2026-12-31T23:30:00Z", "Australia/Sydney")
        conn.commit()
    finally:
        conn.close()
    assert serial.startswith("CERT-ACM-2027-"), serial


def test_list_rows_expose_the_tenant_local_date(acme: TestClient) -> None:
    row = acme.get("/api/certificates", params={"pageSize": 1}).json()["rows"][0]
    assert row["issuedLocalDate"] == local_date(row["issuedAt"], "Australia/Sydney")
    assert len(row["issuedLocalDate"]) == 10
