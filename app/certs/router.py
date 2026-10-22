"""Certificate endpoints. All of them run against the tenant database of the caller's session."""

from __future__ import annotations

import csv
import io
import sqlite3
from typing import Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..auth import Principal, current_principal, require_admin, tenant_db
from ..errors import not_found
from ..timezones import utc_now
from . import repo, service

router = APIRouter(prefix="/api", tags=["certificates"])


class BulkIssueBody(BaseModel):
    courseId: str
    idempotencyKey: str = Field(min_length=8)


class RevokeBody(BaseModel):
    reason: str = Field(min_length=5)


@router.get("/certificates")
def list_certificates(
    search: str = "",
    status: Literal["all", "valid", "revoked"] = "all",
    courseId: str | None = None,
    sort: Literal["learner", "course", "serial", "issuedDate", "status"] = "issuedDate",
    dir: Literal["asc", "desc"] = "desc",
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    principal: Principal = Depends(current_principal),
    conn: sqlite3.Connection = Depends(tenant_db),
) -> dict:
    rows, total = repo.list_certificates(
        conn,
        search=search,
        status=status,
        course_id=courseId,
        sort=sort,
        direction=dir,
        page=page,
        page_size=pageSize,
    )
    return {"rows": rows, "total": total, "page": page, "pageSize": pageSize}


@router.get("/certificates/export.csv")
def export_csv(
    search: str = "",
    status: Literal["all", "valid", "revoked"] = "all",
    courseId: str | None = None,
    principal: Principal = Depends(current_principal),
    conn: sqlite3.Connection = Depends(tenant_db),
) -> StreamingResponse:
    total = repo.count_export(conn, search=search, status=status, course_id=courseId)
    filename = f"certificates-{principal.tenant_code.lower()}-{utc_now().strftime('%Y-%m-%d')}.csv"

    def rows():
        buffer = io.StringIO()
        writer = csv.writer(buffer, quoting=csv.QUOTE_MINIMAL, lineterminator="\r\n")
        buffer.write("\ufeff")
        writer.writerow(["Learner name", "Course title", "Serial number", "Issue date"])
        yield buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)
        for row in repo.iter_export(conn, search=search, status=status, course_id=courseId):
            writer.writerow([row["learner_name"], row["course_title"], row["serial"], row["issued_local_date"]])
            yield buffer.getvalue()
            buffer.seek(0)
            buffer.truncate(0)

    return StreamingResponse(
        rows(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Total-Count": str(total),
        },
    )


@router.get("/certificates/{cert_id}")
def certificate_detail(
    cert_id: str,
    principal: Principal = Depends(current_principal),
    conn: sqlite3.Connection = Depends(tenant_db),
) -> dict:
    detail = repo.get_certificate(conn, cert_id)
    if detail is None:
        raise not_found("Certificate")
    return detail


@router.post("/certificates/bulk-issue")
def bulk_issue(
    body: BulkIssueBody,
    principal: Principal = Depends(require_admin),
    conn: sqlite3.Connection = Depends(tenant_db),
) -> dict:
    return service.bulk_issue(
        conn,
        tenant_code=principal.tenant_code,
        timezone=principal.timezone,
        actor_id=principal.user_id,
        actor_name=principal.user_name,
        course_id=body.courseId,
        idempotency_key=body.idempotencyKey,
    )


@router.post("/certificates/{cert_id}/revoke")
def revoke(
    cert_id: str,
    body: RevokeBody,
    principal: Principal = Depends(require_admin),
    conn: sqlite3.Connection = Depends(tenant_db),
) -> dict:
    service.revoke(
        conn,
        certificate_id=cert_id,
        actor_id=principal.user_id,
        actor_name=principal.user_name,
        reason=body.reason,
    )
    detail = repo.get_certificate(conn, cert_id)
    if detail is None:  # pragma: no cover - just revoked it
        raise not_found("Certificate")
    return detail["certificate"]


@router.post("/certificates/{cert_id}/notify")
def notify(
    cert_id: str,
    principal: Principal = Depends(require_admin),
    conn: sqlite3.Connection = Depends(tenant_db),
) -> dict:
    return service.resend_notification(conn, certificate_id=cert_id, actor_id=principal.user_id)


@router.get("/courses")
def list_courses(
    principal: Principal = Depends(current_principal),
    conn: sqlite3.Connection = Depends(tenant_db),
) -> list[dict]:
    return repo.courses(conn)


@router.get("/courses/{course_id}/eligibility")
def course_eligibility(
    course_id: str,
    principal: Principal = Depends(current_principal),
    conn: sqlite3.Connection = Depends(tenant_db),
) -> dict:
    result = repo.eligibility(conn, course_id)
    if result is None:
        raise not_found("Course")
    return result
