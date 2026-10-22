"""Playwright walkthrough fixtures.

The demo runs against a freshly seeded pair of databases and the built SPA, served by one uvicorn
process on an ephemeral port — the same shape as production, so cookies and routing are real.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.seed import seed  # noqa: E402


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="session")
def base_url(tmp_path_factory) -> str:
    data = tmp_path_factory.mktemp("e2e-data")
    seed(data)

    dist = ROOT / "frontend" / "dist"
    if not dist.exists():
        pytest.skip("frontend/dist is missing — run `npm run build` in frontend/ first")

    port = _free_port()
    env = {**os.environ, "CERT_CONSOLE_DATA": str(data), "PYTHONPATH": str(ROOT)}
    # A PIPE with no reader can fill (especially on Windows) and block uvicorn's
    # access logger and the requests themselves. Keep diagnostics in a real file.
    server_log = (data / "server.log").open("w", encoding="utf-8")
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=ROOT,
        env=env,
        stdout=server_log,
        stderr=subprocess.STDOUT,
    )

    url = f"http://127.0.0.1:{port}"
    deadline = time.time() + 40
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{url}/api/health", timeout=1) as response:
                if response.status == 200:
                    break
        except (urllib.error.URLError, ConnectionError):
            time.sleep(0.25)
    else:  # pragma: no cover
        process.kill()
        process.wait(timeout=5)
        server_log.close()
        raise RuntimeError(f"uvicorn did not become healthy; see {data / 'server.log'}")

    try:
        yield url
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:  # pragma: no cover
            process.kill()
            process.wait(timeout=5)
        server_log.close()
