from __future__ import annotations

import csv
import io

from fastapi.testclient import TestClient


def _parse(response) -> list[list[str]]:
    assert response.content.startswith(b"\xef\xbb\xbf"), "export must be BOM-prefixed UTF-8"
    text = response.content.decode("utf-8-sig")
    return list(csv.reader(io.StringIO(text)))


def test_export_matches_list_total(acme: TestClient) -> None:
    total = acme.get("/api/certificates", params={"pageSize": 1}).json()["total"]
    response = acme.get("/api/certificates/export.csv")
    assert response.status_code == 200
    assert response.headers["x-total-count"] == str(total)

    rows = _parse(response)
    assert rows[0] == ["Learner name", "Course title", "Serial number", "Issue date"]
    assert len(rows) - 1 == total


def test_export_respects_the_filter(acme: TestClient) -> None:
    response = acme.get("/api/certificates/export.csv", params={"status": "revoked"})
    rows = _parse(response)
    assert len(rows) - 1 == 1
    assert rows[1][2].startswith("CERT-ACM-")


def test_export_dates_are_tenant_local(acme: TestClient) -> None:
    rows = _parse(acme.get("/api/certificates/export.csv", params={"pageSize": 5}))
    for row in rows[1:]:
        assert len(row[3]) == 10 and row[3][4] == "-" and row[3][7] == "-", row[3]


def test_export_quotes_commas(acme: TestClient) -> None:
    # Course titles contain no commas today, but the writer must be RFC4180-correct anyway.
    response = acme.get("/api/certificates/export.csv")
    text = response.content.decode("utf-8-sig")
    for line in text.strip().split("\r\n"):
        assert line.count('"') % 2 == 0, line


def test_export_is_scoped_to_the_tenant(northwind: TestClient) -> None:
    rows = _parse(northwind.get("/api/certificates/export.csv"))
    for row in rows[1:]:
        assert row[2].startswith("CERT-NWL-")


def test_export_stream_survives_request_dependency_cleanup(app):
    import asyncio
    import csv
    import io
    from types import SimpleNamespace
    from app.certs.router import export_csv
    databases = app.state.databases
    conn = databases.tenant("ACM")
    expected = conn.execute("select count(*) from certificate").fetchone()[0]
    response = export_csv(search="", status="all", courseId=None,
                          principal=SimpleNamespace(tenant_code="ACM"),
                          conn=conn, databases=databases)
    conn.close()  # Simulate FastAPI 0.115 cleaning up request dependencies.
    async def consume():
        return "".join([chunk async for chunk in response.body_iterator])
    rows = list(csv.reader(io.StringIO(asyncio.run(consume()).lstrip("\ufeff"))))
    assert len(rows) - 1 == expected
