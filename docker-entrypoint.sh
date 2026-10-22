#!/bin/sh
set -eu
python -m app.bootstrap "${CERT_CONSOLE_DATA:-/data}"
exec python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
