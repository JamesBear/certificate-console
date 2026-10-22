"""Session authentication.

The tenant is never accepted from the client. A session row binds a user to a tenant; the request
reads that binding and opens the matching tenant database. Cross-tenant lookups are 404, because
the row simply does not exist in the database the request can reach.
"""

from __future__ import annotations

import hashlib
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import timedelta

from fastapi import APIRouter, Cookie, Depends, Request, Response
from pydantic import BaseModel

from .db import Databases
from .errors import ApiError, forbidden, not_found
from .timezones import to_iso, utc_now, zone_abbr

SESSION_COOKIE = "session"
SESSION_TTL = timedelta(hours=12)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@dataclass(frozen=True)
class Principal:
    user_id: str
    user_name: str
    role: str
    tenant_id: str
    tenant_name: str
    tenant_code: str
    timezone: str


def get_databases(request: Request) -> Databases:
    return request.app.state.databases


def control_connection(databases: Databases = Depends(get_databases)):
    conn = databases.control()
    try:
        yield conn
    finally:
        conn.close()


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def current_principal(
    request: Request,
    session: str | None = Cookie(default=None),
) -> Principal:
    if not session:
        raise ApiError("unauthenticated", "Sign in to continue.", 401)

    databases: Databases = request.app.state.databases
    conn = databases.control()
    try:
        row = conn.execute(
            """
            select s.token_hash, s.expires_at, s.user_id, u.name as user_name, m.role,
                   t.id as tenant_id, t.name as tenant_name, t.code as tenant_code, t.timezone
            from session s
            join app_user u on u.id = s.user_id
            join membership m on m.user_id = s.user_id and m.tenant_id = s.tenant_id
            join tenant t on t.id = s.tenant_id
            where s.token_hash = ?
            """,
            (_hash(session),),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        raise ApiError("unauthenticated", "Session expired. Sign in again.", 401)
    if row["expires_at"] <= to_iso(utc_now()):
        raise ApiError("unauthenticated", "Session expired. Sign in again.", 401)

    return Principal(
        user_id=row["user_id"],
        user_name=row["user_name"],
        role=row["role"],
        tenant_id=row["tenant_id"],
        tenant_name=row["tenant_name"],
        tenant_code=row["tenant_code"],
        timezone=row["timezone"],
    )


def tenant_db(
    request: Request,
    principal: Principal = Depends(current_principal),
):
    databases: Databases = request.app.state.databases
    conn = databases.tenant(principal.tenant_code)
    try:
        yield conn
    finally:
        conn.close()


def require_admin(principal: Principal = Depends(current_principal)) -> Principal:
    if principal.role != "admin":
        raise forbidden("Only tenant admins can do that.")
    return principal


class LoginBody(BaseModel):
    tenantId: str
    userId: str


@router.get("/tenants")
def list_tenants(conn: sqlite3.Connection = Depends(control_connection)) -> list[dict]:
    rows = conn.execute("select id, name, code, timezone from tenant order by name").fetchall()
    return [dict(row) for row in rows]


@router.get("/accounts")
def list_accounts(tenant_id: str, conn: sqlite3.Connection = Depends(control_connection)) -> list[dict]:
    rows = conn.execute(
        """
        select u.id, u.name, m.role
        from membership m
        join app_user u on u.id = m.user_id
        join tenant t on t.id = m.tenant_id
        where t.id = ?
        order by u.name
        """,
        (tenant_id,),
    ).fetchall()
    return [dict(row) for row in rows]


@router.post("/login")
def login(
    body: LoginBody,
    response: Response,
    databases: Databases = Depends(get_databases),
    conn: sqlite3.Connection = Depends(control_connection),
) -> dict:
    row = conn.execute(
        """
        select m.role, u.id as user_id, u.name as user_name,
               t.id as tenant_id, t.name as tenant_name, t.code as tenant_code, t.timezone
        from membership m
        join app_user u on u.id = m.user_id
        join tenant t on t.id = m.tenant_id
        where m.tenant_id = ? and m.user_id = ?
        """,
        (body.tenantId, body.userId),
    ).fetchone()
    if row is None:
        raise not_found("Account")

    token = secrets.token_urlsafe(32)
    now = utc_now()
    conn.execute("begin immediate")
    try:
        conn.execute(
            "insert into session (token_hash, user_id, tenant_id, created_at, expires_at) values (?, ?, ?, ?, ?)",
            (_hash(token), row["user_id"], row["tenant_id"], to_iso(now), to_iso(now + SESSION_TTL)),
        )
        conn.execute("commit")
    except Exception:
        conn.execute("rollback")
        raise

    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        samesite="lax",
        max_age=int(SESSION_TTL.total_seconds()),
        path="/",
    )
    return {
        "user": {"id": row["user_id"], "name": row["user_name"]},
        "tenant": {
            "id": row["tenant_id"],
            "name": row["tenant_name"],
            "code": row["tenant_code"],
            "timezone": row["timezone"],
        },
        "role": row["role"],
    }


@router.post("/logout")
def logout(
    response: Response,
    session: str | None = Cookie(default=None),
    conn: sqlite3.Connection = Depends(control_connection),
) -> dict:
    if session:
        conn.execute("delete from session where token_hash = ?", (_hash(session),))
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}


@router.get("/me")
def me(principal: Principal = Depends(current_principal)) -> dict:
    return {
        "user": {"id": principal.user_id, "name": principal.user_name},
        "tenant": {
            "id": principal.tenant_id,
            "name": principal.tenant_name,
            "code": principal.tenant_code,
            "timezone": principal.timezone,
        },
        "role": principal.role,
        "zoneAbbr": zone_abbr(principal.timezone),
    }
