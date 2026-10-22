from __future__ import annotations

from fastapi.testclient import TestClient


def test_first_page_shape(acme: TestClient) -> None:
    body = acme.get("/api/certificates", params={"pageSize": 10}).json()
    assert body["total"] > 10
    assert len(body["rows"]) == 10
    assert set(body["rows"][0]) >= {
        "id",
        "learnerName",
        "courseTitle",
        "serial",
        "issuedAt",
        "issuedLocalDate",
        "status",
        "notificationStatus",
    }


def test_pagination_is_stable(acme: TestClient) -> None:
    first = acme.get("/api/certificates", params={"pageSize": 10, "page": 1}).json()
    second = acme.get("/api/certificates", params={"pageSize": 10, "page": 2}).json()
    assert first["total"] == second["total"]
    assert {row["id"] for row in first["rows"]}.isdisjoint({row["id"] for row in second["rows"]})


def test_search_by_learner_name(acme: TestClient) -> None:
    row = acme.get("/api/certificates", params={"pageSize": 1}).json()["rows"][0]
    surname = row["learnerName"].split()[-1].lower()
    found = acme.get("/api/certificates", params={"search": surname, "pageSize": 100}).json()
    assert found["total"] >= 1
    assert all(surname in item["learnerName"].lower() for item in found["rows"])


def test_search_by_serial_fragment(acme: TestClient) -> None:
    row = acme.get("/api/certificates", params={"pageSize": 1}).json()["rows"][0]
    fragment = row["serial"][-5:]
    found = acme.get("/api/certificates", params={"search": fragment, "pageSize": 100}).json()
    assert found["total"] >= 1
    assert any(item["serial"] == row["serial"] for item in found["rows"])


def test_no_match_returns_empty_page_not_error(acme: TestClient) -> None:
    body = acme.get("/api/certificates", params={"search": "zzzz-not-a-learner"}).json()
    assert body["total"] == 0
    assert body["rows"] == []


def test_status_filter(acme: TestClient) -> None:
    body = acme.get("/api/certificates", params={"status": "revoked", "pageSize": 100}).json()
    assert body["total"] == 1
    assert body["rows"][0]["status"] == "revoked"


def test_sort_by_learner_and_serial(acme: TestClient) -> None:
    by_name = acme.get("/api/certificates", params={"sort": "learner", "dir": "asc", "pageSize": 50}).json()["rows"]
    names = [row["learnerName"].lower() for row in by_name]
    assert names == sorted(names)

    by_serial = acme.get("/api/certificates", params={"sort": "serial", "dir": "asc", "pageSize": 50}).json()["rows"]
    serials = [row["serial"] for row in by_serial]
    assert serials == sorted(serials)


def test_sort_by_issued_date_uses_local_date(acme: TestClient) -> None:
    rows = acme.get(
        "/api/certificates", params={"sort": "issuedDate", "dir": "asc", "pageSize": 100}
    ).json()["rows"]
    dates = [row["issuedLocalDate"] for row in rows]
    assert dates == sorted(dates)


def test_course_filter(acme: TestClient) -> None:
    courses = acme.get("/api/courses").json()
    course_id = courses[0]["id"]
    rows = acme.get("/api/certificates", params={"courseId": course_id, "pageSize": 100}).json()["rows"]
    assert rows
    assert all(row["courseId"] == course_id for row in rows)
