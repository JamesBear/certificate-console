from __future__ import annotations

from fastapi.testclient import TestClient


def _revoked_id(client: TestClient) -> str:
    return client.get("/api/certificates", params={"status": "revoked", "pageSize": 1}).json()["rows"][0]["id"]


def _valid_id(client: TestClient) -> str:
    return client.get("/api/certificates", params={"status": "valid", "pageSize": 1}).json()["rows"][0]["id"]


def test_detail_carries_the_audit_trail(acme: TestClient) -> None:
    body = acme.get(f"/api/certificates/{_revoked_id(acme)}").json()
    assert body["certificate"]["status"] == "revoked"
    actions = [entry["action"] for entry in body["audit"]]
    assert actions.count("issued") == 1
    assert actions.count("revoked") == 1
    assert body["learner"]["name"]
    assert body["course"]["title"]


def test_unknown_certificate_is_404(acme: TestClient) -> None:
    assert acme.get("/api/certificates/crt_does_not_exist").status_code == 404


def test_revoke_writes_status_and_audit(acme: TestClient) -> None:
    cert_id = _valid_id(acme)
    response = acme.post(f"/api/certificates/{cert_id}/revoke", json={"reason": "Wrong batch issued."})
    assert response.status_code == 200
    assert response.json()["status"] == "revoked"

    detail = acme.get(f"/api/certificates/{cert_id}").json()
    assert detail["certificate"]["revokeReason"] == "Wrong batch issued."
    assert [entry["action"] for entry in detail["audit"]].count("revoked") == 1
    assert any(
        entry["action"] == "revoked" and entry["actorId"] == "u_t_acme" for entry in detail["audit"]
    )


def test_double_revoke_is_409(acme: TestClient) -> None:
    cert_id = _valid_id(acme)
    assert acme.post(f"/api/certificates/{cert_id}/revoke", json={"reason": "first reason"}).status_code == 200
    second = acme.post(f"/api/certificates/{cert_id}/revoke", json={"reason": "second reason"})
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "already_revoked"


def test_revoke_requires_a_real_reason(acme: TestClient) -> None:
    cert_id = _valid_id(acme)
    assert acme.post(f"/api/certificates/{cert_id}/revoke", json={"reason": "no"}).status_code == 422


def test_viewer_cannot_revoke(viewer: TestClient) -> None:
    cert_id = _valid_id(viewer)
    assert viewer.post(f"/api/certificates/{cert_id}/revoke", json={"reason": "not allowed"}).status_code == 403


def test_revoked_certificate_keeps_its_serial(acme: TestClient) -> None:
    cert_id = _revoked_id(acme)
    detail = acme.get(f"/api/certificates/{cert_id}").json()
    assert detail["certificate"]["serial"].startswith("CERT-ACM-")
    assert detail["learner"]["id"]


def test_resend_sets_notification_state(acme: TestClient) -> None:
    cert_id = _valid_id(acme)
    response = acme.post(f"/api/certificates/{cert_id}/notify")
    assert response.status_code == 200
    assert response.json()["notificationStatus"] == "sent"

    detail = acme.get(f"/api/certificates/{cert_id}").json()
    assert detail["certificate"]["notificationStatus"] == "sent"
    assert "notified" in [entry["action"] for entry in detail["audit"]]
