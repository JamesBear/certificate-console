from __future__ import annotations

from fastapi.testclient import TestClient


def test_unauthenticated_list_is_401(client: TestClient) -> None:
    response = client.get("/api/certificates")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"


def test_login_sets_session_and_returns_identity(client: TestClient) -> None:
    response = client.post("/api/auth/login", json={"tenantId": "t_acme", "userId": "u_t_acme"})
    assert response.status_code == 200
    assert response.json()["tenant"]["timezone"] == "Australia/Sydney"
    assert response.json()["role"] == "admin"
    assert "session" in response.cookies

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["tenant"]["code"] == "ACM"


def test_logout_invalidates_session(client: TestClient) -> None:
    client.post("/api/auth/login", json={"tenantId": "t_acme", "userId": "u_t_acme"})
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/auth/me").status_code == 401


def test_login_rejects_account_from_another_tenant(client: TestClient) -> None:
    response = client.post("/api/auth/login", json={"tenantId": "t_acme", "userId": "u_t_northwind"})
    assert response.status_code == 404


def test_accounts_are_scoped_to_their_tenant(client: TestClient) -> None:
    acme = client.get("/api/auth/accounts", params={"tenant_id": "t_acme"}).json()
    meridian = client.get("/api/auth/accounts", params={"tenant_id": "t_meridian"}).json()
    assert [row["id"] for row in acme] == ["u_viewer_acme", "u_t_acme"]
    assert [row["id"] for row in meridian] == ["u_t_meridian"]


def test_viewer_role_cannot_revoke(client: TestClient) -> None:
    client.post("/api/auth/login", json={"tenantId": "t_acme", "userId": "u_viewer_acme"})
    rows = client.get("/api/certificates", params={"pageSize": 1}).json()["rows"]
    response = client.post(f"/api/certificates/{rows[0]['id']}/revoke", json={"reason": "should not work"})
    assert response.status_code == 403
