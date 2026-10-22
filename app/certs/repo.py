"""Read queries. Every function takes a tenant database connection — there is no global one."""

from __future__ import annotations

import sqlite3
from typing import Iterable

SORT_COLUMNS = {
    "learner": "l.name collate nocase",
    "course": "co.title collate nocase",
    "serial": "c.serial",
    "issuedDate": "c.issued_local_date",
    "status": "c.status",
}

FILTER_SQL = """
from certificate c
join learner l on l.id = c.learner_id
join course co on co.id = c.course_id
where 1 = 1
"""


def _filters(search: str, status: str, course_id: str | None) -> tuple[str, list]:
    sql = ""
    params: list = []
    term = search.strip().lower()
    if term:
        sql += " and (lower(l.name) like ? or lower(c.serial) like ?)"
        params.extend([f"%{term}%", f"%{term}%"])
    if status in ("valid", "revoked"):
        sql += " and c.status = ?"
        params.append(status)
    if course_id:
        sql += " and c.course_id = ?"
        params.append(course_id)
    return sql, params


def _row(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "learnerName": row["learner_name"],
        "learnerEmail": row["learner_email"],
        "courseTitle": row["course_title"],
        "courseId": row["course_id"],
        "serial": row["serial"],
        "issuedAt": row["issued_at"],
        "issuedLocalDate": row["issued_local_date"],
        "status": row["status"],
        "notificationStatus": row["notification_status"],
    }


def list_certificates(
    conn: sqlite3.Connection,
    *,
    search: str = "",
    status: str = "all",
    course_id: str | None = None,
    sort: str = "issuedDate",
    direction: str = "desc",
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict], int]:
    where, params = _filters(search, status, course_id)
    total = conn.execute(f"select count(*) {FILTER_SQL}{where}", params).fetchone()[0]

    column = SORT_COLUMNS.get(sort, SORT_COLUMNS["issuedDate"])
    order = f"{column} {'asc' if direction == 'asc' else 'desc'}"
    if sort == "issuedDate":
        order += f", c.issued_at {'asc' if direction == 'asc' else 'desc'}"
    else:
        order += ", c.issued_at desc"

    rows = conn.execute(
        f"""
        select c.*, l.name as learner_name, l.email as learner_email, co.title as course_title
        {FILTER_SQL}{where}
        order by {order}
        limit ? offset ?
        """,
        params + [page_size, (page - 1) * page_size],
    ).fetchall()
    return [_row(row) for row in rows], total


def iter_export(conn: sqlite3.Connection, *, search: str, status: str, course_id: str | None) -> Iterable[sqlite3.Row]:
    where, params = _filters(search, status, course_id)
    cursor = conn.execute(
        f"""
        select c.serial, c.issued_local_date, l.name as learner_name, co.title as course_title
        {FILTER_SQL}{where}
        order by c.issued_local_date asc, c.issued_at asc, c.serial asc
        """,
        params,
    )
    yield from cursor


def count_export(conn: sqlite3.Connection, *, search: str, status: str, course_id: str | None) -> int:
    where, params = _filters(search, status, course_id)
    return conn.execute(f"select count(*) {FILTER_SQL}{where}", params).fetchone()[0]


def get_certificate(conn: sqlite3.Connection, cert_id: str) -> dict | None:
    row = conn.execute(
        """
        select c.*, l.name as learner_name, l.email as learner_email, co.title as course_title,
               co.code as course_code
        from certificate c
        join learner l on l.id = c.learner_id
        join course co on co.id = c.course_id
        where c.id = ?
        """,
        (cert_id,),
    ).fetchone()
    if row is None:
        return None
    return {
        "certificate": {
            "id": row["id"],
            "serial": row["serial"],
            "courseId": row["course_id"],
            "learnerId": row["learner_id"],
            "issuedAt": row["issued_at"],
            "issuedLocalDate": row["issued_local_date"],
            "issuedBy": row["issued_by"],
            "status": row["status"],
            "notificationStatus": row["notification_status"],
            "notificationSentAt": row["notification_sent_at"],
            "revokedAt": row["revoked_at"],
            "revokedBy": row["revoked_by"],
            "revokeReason": row["revoke_reason"],
        },
        "learner": {"id": row["learner_id"], "name": row["learner_name"], "email": row["learner_email"]},
        "course": {"id": row["course_id"], "code": row["course_code"], "title": row["course_title"]},
        "audit": audit_for(conn, cert_id),
    }


def audit_for(conn: sqlite3.Connection, cert_id: str) -> list[dict]:
    rows = conn.execute(
        """
        select id, action, actor_user_id, at, detail
        from audit_entry where certificate_id = ? order by at desc, id desc
        """,
        (cert_id,),
    ).fetchall()
    return [
        {"id": row["id"], "action": row["action"], "actorId": row["actor_user_id"], "at": row["at"], "detail": row["detail"]}
        for row in rows
    ]


def courses(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """
        select co.id, co.code, co.title,
               (select count(*) from enrollment e where e.course_id = co.id) as enrolled
        from course co order by co.title
        """
    ).fetchall()
    return [dict(row) for row in rows]


def eligibility(conn: sqlite3.Connection, course_id: str) -> dict | None:
    exists = conn.execute("select 1 from course where id = ?", (course_id,)).fetchone()
    if exists is None:
        return None
    enrolled = conn.execute(
        "select count(*) from enrollment where course_id = ?", (course_id,)
    ).fetchone()[0]
    completed = conn.execute(
        "select count(*) from enrollment where course_id = ? and completed_at is not null", (course_id,)
    ).fetchone()[0]
    already = conn.execute(
        """
        select count(*) from enrollment e
        join certificate c on c.course_id = e.course_id and c.learner_id = e.learner_id
        where e.course_id = ? and e.completed_at is not null
        """,
        (course_id,),
    ).fetchone()[0]
    return {"enrolled": enrolled, "eligible": completed - already, "alreadyIssued": already}
