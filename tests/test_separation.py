from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from app.db import Databases


def test_each_tenant_has_its_own_database_file(seeded: Path) -> None:
    files = {path.name for path in (seeded / "tenants").glob("*.db")}
    assert files == {"acm.db", "nwl.db", "mrh.db"}


def test_tenant_databases_have_no_tenant_column(seeded: Path) -> None:
    conn = sqlite3.connect(seeded / "tenants" / "acm.db")
    try:
        tables = [row[0] for row in conn.execute("select name from sqlite_master where type = 'table'")]
        for table in ("certificate", "course", "learner", "enrollment", "audit_entry"):
            assert table in tables
            columns = [row[1] for row in conn.execute(f"pragma table_info({table})")]
            assert "tenant_id" not in columns, f"{table} must not carry tenant_id"
    finally:
        conn.close()


def test_control_database_holds_no_domain_data(seeded: Path) -> None:
    conn = sqlite3.connect(seeded / "control.db")
    try:
        tables = {row[0] for row in conn.execute("select name from sqlite_master where type = 'table'")}
    finally:
        conn.close()
    assert {"tenant", "app_user", "membership", "session"} <= tables
    assert not {"certificate", "course", "learner"} & tables


def test_certificate_from_another_tenant_is_404(acme: TestClient, northwind: TestClient) -> None:
    northwind_rows = northwind.get("/api/certificates", params={"pageSize": 1}).json()["rows"]
    foreign_id = northwind_rows[0]["id"]

    response = acme.get(f"/api/certificates/{foreign_id}")
    assert response.status_code == 404
    assert acme.post(f"/api/certificates/{foreign_id}/revoke", json={"reason": "nope nope"}).status_code == 404


def test_lists_never_mix_tenants(acme: TestClient, northwind: TestClient) -> None:
    acme_serials = {row["serial"] for row in acme.get("/api/certificates", params={"pageSize": 100}).json()["rows"]}
    northwind_serials = {
        row["serial"] for row in northwind.get("/api/certificates", params={"pageSize": 100}).json()["rows"]
    }
    assert acme_serials and northwind_serials
    assert all(serial.startswith("CERT-ACM-") for serial in acme_serials)
    assert all(serial.startswith("CERT-NWL-") for serial in northwind_serials)
    assert not acme_serials & northwind_serials


def test_tenant_database_path_cannot_escape(seeded: Path) -> None:
    databases = Databases(seeded)
    try:
        databases.tenant("../control")
    except Exception as exc:  # noqa: BLE001 - the point is that it refuses
        assert "path" in str(exc).lower() or "invalid" in str(exc).lower()
    else:  # pragma: no cover
        raise AssertionError("expected a refusal for a path outside the tenants directory")
