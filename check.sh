#!/bin/sh
# Project gate. `task gate` runs this and only looks at the exit code.
set -eu

python -m compileall -q app > /dev/null
echo "compile: ok"

python -m pytest -q tests

if [ -f frontend/node_modules/typescript/bin/tsc ]; then
  (cd frontend && node node_modules/typescript/bin/tsc --noEmit)
  echo "frontend typecheck: ok"
fi

echo "check: ok"
