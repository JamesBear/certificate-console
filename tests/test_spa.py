"""SPA routing must never expose files outside its build directory."""
import pytest
from fastapi.testclient import TestClient
import app.main as main


@pytest.fixture()
def spa(tmp_path, monkeypatch):
    dist = tmp_path / "frontend" / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>console</html>")
    (tmp_path / "private.txt").write_text("must never be public")
    monkeypatch.setattr(main, "FRONTEND_DIST", dist)
    with TestClient(main.create_app(tmp_path / "data")) as client:
        yield client


def test_encoded_parent_traversal_is_rejected(spa):
    response = spa.get("/%2e%2e/%2e%2e/private.txt")
    assert response.status_code == 404
    assert "must never be public" not in response.text


def test_normal_client_route_still_serves_spa(spa):
    response = spa.get("/certificates/example")
    assert response.status_code == 200
    assert response.text == "<html>console</html>"
