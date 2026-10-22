#!/bin/sh
# Seed only when there is no control database yet: restarting must not wipe state.
set -eu

DATA="${CERT_CONSOLE_DATA:-/data}"
if [ ! -f "$DATA/control.db" ]; then
  echo "[entrypoint] seeding demo data into $DATA"
  python -m app.seed "$DATA"
else
  echo "[entrypoint] using existing data in $DATA"
fi

exec uvicorn app.main:app --host 0.0.0.0 --port 8000
