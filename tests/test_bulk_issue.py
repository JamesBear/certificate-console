from __future__ import annotations

from fastapi.testclient import TestClient

FAR_330 = "c_acm_3"  # seeded with nobody certified, so it always has eligible learners
NO_EMAIL_LEARNER = "Ethan Walsh"


def _preview(client: TestClient, course_id: str = FAR_330) -> dict:
    return client.get(f"/api/courses/{course_id}/eligibility").json()


def _total(client: TestClient) -> int:
    return client.get("/api/certificates", params={"pageSize": 1}).json()["total"]


def test_eligibility_preview(acme: TestClient) -> None:
    preview = _preview(acme)
    assert preview["eligible"] > 0
    assert preview["alreadyIssued"] == 0
    assert preview["enrolled"] >= preview["eligible"]


def test_bulk_issue_issues_every_eligible_learner(acme: TestClient) -> None:
    before = _total(acme)
    eligible = _preview(acme)["eligible"]

    response = acme.post(
        "/api/certificates/bulk-issue",
        json={"courseId": FAR_330, "idempotencyKey": "test-key-0001"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["replay"] is False
    assert body["summary"]["issued"] == eligible
    assert _total(acme) == before + eligible

    issued = [row for row in body["rows"] if row["outcome"] == "issued"]
    assert all(row["serial"].startswith("CERT-ACM-") for row in issued)
    statuses = {row["outcome"] for row in body["rows"]}
    assert statuses == {"issued"}


def test_learner_without_email_gets_a_certificate_and_a_skipped_notification(acme: TestClient) -> None:
    acme.post("/api/certificates/bulk-issue", json={"courseId": FAR_330, "idempotencyKey": "test-key-0002"})
    rows = acme.get("/api/certificates", params={"search": NO_EMAIL_LEARNER, "pageSize": 100}).json()["rows"]
    matches = [row for row in rows if row["learnerName"] == NO_EMAIL_LEARNER]
    assert matches, "the learner without an email should still receive a certificate"
    assert any(row["notificationStatus"] == "skipped" for row in matches), matches


def test_replay_returns_the_original_result_and_writes_nothing(acme: TestClient) -> None:
    acme.post("/api/certificates/bulk-issue", json={"courseId": FAR_330, "idempotencyKey": "test-key-0003"})
    after_first = _total(acme)

    replay = acme.post(
        "/api/certificates/bulk-issue", json={"courseId": FAR_330, "idempotencyKey": "test-key-0003"}
    ).json()
    assert replay["replay"] is True
    assert _total(acme) == after_first


def test_a_different_key_is_blocked_by_the_unique_index(acme: TestClient) -> None:
    acme.post("/api/certificates/bulk-issue", json={"courseId": FAR_330, "idempotencyKey": "test-key-0004"})
    after_first = _total(acme)

    second = acme.post(
        "/api/certificates/bulk-issue", json={"courseId": FAR_330, "idempotencyKey": "test-key-0005"}
    ).json()
    assert second["replay"] is False
    assert second["summary"]["issued"] == 0
    assert second["summary"]["skipped"] == len(second["rows"])
    assert _total(acme) == after_first


def test_every_issuance_writes_one_audit_row(acme: TestClient) -> None:
    body = acme.post(
        "/api/certificates/bulk-issue", json={"courseId": FAR_330, "idempotencyKey": "test-key-0006"}
    ).json()
    issued = [row for row in body["rows"] if row["outcome"] == "issued"][:3]

    for row in issued:
        cert_id = row["learnerId"]
        found = acme.get("/api/certificates", params={"search": row["serial"], "pageSize": 1}).json()["rows"][0]
        detail = acme.get(f"/api/certificates/{found['id']}").json()
        assert [entry["action"] for entry in detail["audit"]].count("issued") == 1
        assert cert_id in detail["certificate"]["learnerId"]


def test_bulk_issue_on_unknown_course_is_404(acme: TestClient) -> None:
    response = acme.post(
        "/api/certificates/bulk-issue", json={"courseId": "c_nope_9", "idempotencyKey": "test-key-0007"}
    )
    assert response.status_code == 404


def test_course_from_another_tenant_is_404(acme: TestClient) -> None:
    response = acme.post(
        "/api/certificates/bulk-issue", json={"courseId": "c_nwl_0", "idempotencyKey": "test-key-0008"}
    )
    assert response.status_code == 404


def test_viewer_cannot_bulk_issue(viewer: TestClient) -> None:
    response = viewer.post(
        "/api/certificates/bulk-issue", json={"courseId": FAR_330, "idempotencyKey": "test-key-0009"}
    )
    assert response.status_code == 403


def test_already_issued_course_reports_skipped(acme: TestClient) -> None:
    acme.post("/api/certificates/bulk-issue", json={"courseId": FAR_330, "idempotencyKey": "test-key-0010"})
    preview = _preview(acme)
    assert preview["eligible"] == 0
    assert preview["alreadyIssued"] > 0
