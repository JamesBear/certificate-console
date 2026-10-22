# Native and Docker startup

## Native

Prerequisites: Python 3.11+ with venv and pip, Node 22 LTS with npm. Verify `python --version`,
`node --version`, and `npm --version`. On distributions with split Python packaging, install the
matching venv package first. No global Python dependency installation is required.

```sh
python run.py
```

First run creates `.venv`, installs pinned Python requirements and the portable npm lockfile, and
seeds an empty workspace. It prints READY only after the API and frontend answer successfully.
Open http://127.0.0.1:5173. Installation stages are visible and bounded by `--setup-timeout` (180s
by default). Do not interpret the running foreground server as a hang: Ctrl+C stops both services.
SIGTERM also stops their process groups on Linux. Occupied ports fail explicitly.

```sh
python run.py --prod                         # built SPA + API on 8000
python run.py --port 18000 --web-port 15173   # custom ports; proxy follows API port
python run.py --no-bootstrap                 # intentionally reuse current Python/dependencies
```

`--no-bootstrap` requires dependencies to be installed already. `--seed` explicitly recreates the
known demo databases. Normal startup does not reset issued/revoked credentials. Never point a demo
seed at production records.

## Docker

```sh
cp .env.example .env
docker compose up --build -d --wait
docker compose ps
docker compose logs -f
docker compose down
```

Open http://127.0.0.1:8000. The container contains the built SPA and Python runtime; no host Node or
Python is required. The data folder is a bind mount, preserved by `down` and recreation. The first
start handles an empty control database as well as a missing database. The mounted folder itself
and unrelated files are never deleted by the seed routine.

The image uses `npm ci` and the committed cross-platform lockfile. `.dockerignore` excludes host
node_modules, virtualenvs, databases and test artifacts. Shell scripts are LF-normalized for Windows
checkouts. Runtime CSV streaming owns its SQLite connection so the pinned FastAPI version can safely
clean up request dependencies before the stream ends.

If public PyPI is slow from the build host, set the optional index/trusted-host variables in `.env`.
On the tested Tencent host, its local mirror was used for the successful image build:

```sh
PIP_INDEX_URL=http://mirrors.tencentyun.com/pypi/simple \
PIP_TRUSTED_HOST=mirrors.tencentyun.com docker compose build
```

The default remains public HTTPS PyPI. Mirror values are build-time configuration, not requirements
for running the finished image. Do not place credentials in build arguments.

## Verified host: root@82.157.63.75 (2026-10-22)

Isolated test checkout: `/srv/verification/certificate-console-startup`.
Second fresh native checkout: `/srv/verification/certificate-console-clean`.
Existing taskhub/Gitea checkouts and services were not modified.

Installed Node 22.23.4 under `/opt/certificate-console-node`, verified against the official SHA256
manifest, with node/npm/npx links in `/usr/local/bin`. Native tests used Python 3.13.12; the Docker
runtime is Python 3.12. Both install the repository's pinned FastAPI 0.115.6.

Verified:
- Literal `python run.py` from the second clean checkout, without .venv or node_modules.
- Development mode with API 18000 and frontend 15173, including the Vite proxy.
- Production mode on 18001 with a built SPA.
- Login, certificate list, bulk issuance, idempotency replay with unchanged row count, revoke/audit,
  filtered CSV row-count parity and logout against each native mode and Docker.
- Native shutdown releases API/frontend ports; populated data survives subsequent startup.
- Compose image builds and container becomes healthy on loopback 18080.
- Compose down releases its port; recreation preserves issued/revoked records and passes smoke again.
- 59 tests pass in the remote Python 3.13 virtualenv and in the Python 3.12 image.

The test Compose project is `certificate-console-verify`; its persistent data folder is `compose-data`.
Its local `.env` records port 18080 and the project name so ordinary compose commands target it.
To view it from your computer:

```sh
ssh -N -L 18080:127.0.0.1:18080 root@82.157.63.75
```

Then open http://127.0.0.1:18080. The verification container is intentionally bound to loopback.
Logs from native runs are `native-dev.log` and `native-prod.log` in the isolated checkout.
