from __future__ import annotations

import shutil
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.main import create_app  # noqa: E402
from app.seed import seed  # noqa: E402


@pytest.fixture(scope="session")
def seeded(tmp_path_factory) -> Path:
    base = tmp_path_factory.mktemp("seeded")
    seed(base)
    return base


@pytest.fixture()
def app(seeded: Path, tmp_path: Path) -> FastAPI:
    # Every test gets its own copy, so revocation / issuance never leak between tests.
    data = tmp_path / "data"
    shutil.copytree(seeded, data)
    return create_app(data)


@pytest.fixture()
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


def login_as(client: TestClient, tenant: str = "t_acme", user: str = "u_t_acme") -> TestClient:
    response = client.post("/api/auth/login", json={"tenantId": tenant, "userId": user})
    assert response.status_code == 200, response.text
    return client


@pytest.fixture()
def acme(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield login_as(test_client)


@pytest.fixture()
def northwind(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield login_as(test_client, "t_northwind", "u_t_northwind")


@pytest.fixture()
def viewer(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield login_as(test_client, "t_acme", "u_viewer_acme")
