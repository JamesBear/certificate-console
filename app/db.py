"""Database access.

Two kinds of file (plan D11):

* ``control.db`` — tenants, users, memberships, sessions. Shared by the console.
* ``tenants/<code>.db`` — one file per tenant, holding that tenant's domain data and nothing else.
  There is no ``tenant_id`` column in these files; one database *is* one tenant.

Every request opens the tenant database selected by its session. A repository that has no tenant
database cannot run a query at all, which is the point.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .errors import ApiError

SCHEMA_DIR = Path(__file__).resolve().parent

CONTROL_SCHEMA_VERSION = 1
TENANT_SCHEMA_VERSION = 1


def _configure(conn: sqlite3.Connection) -> sqlite3.Connection:
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.isolation_level = None  # explicit BEGIN/COMMIT
    return conn


def _apply_schema(conn: sqlite3.Connection, schema_file: str, version: int) -> None:
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    if current >= version:
        return
    sql = (SCHEMA_DIR / schema_file).read_text(encoding="utf-8")
    conn.executescript(sql)
    conn.execute(f"PRAGMA user_version = {version}")


class Databases:
    def __init__(self, base: str | Path) -> None:
        self.base = Path(base).resolve()
        self.base.mkdir(parents=True, exist_ok=True)
        self.control_path = self.base / "control.db"
        self.tenants_dir = self.base / "tenants"
        self.tenants_dir.mkdir(parents=True, exist_ok=True)

    def _connect(self, path: Path) -> sqlite3.Connection:
        # FastAPI may run a synchronous dependency, endpoint and cleanup on different
        # worker threads. Connections remain request-scoped; never shared between requests.
        return _configure(sqlite3.connect(path, check_same_thread=False))

    def control(self) -> sqlite3.Connection:
        conn = self._connect(self.control_path)
        _apply_schema(conn, "schema_control.sql", CONTROL_SCHEMA_VERSION)
        return conn

    def tenant_path(self, code: str) -> Path:
        path = (self.tenants_dir / f"{code.lower()}.db").resolve()
        try:
            path.relative_to(self.tenants_dir)
        except ValueError as exc:  # pragma: no cover - defensive
            raise ApiError("invalid_tenant", "Invalid tenant database path.", 500) from exc
        return path

    def tenant(self, code: str) -> sqlite3.Connection:
        conn = self._connect(self.tenant_path(code))
        _apply_schema(conn, "schema_tenant.sql", TENANT_SCHEMA_VERSION)
        return conn
