#!/bin/sh
# Project gate. `task gate` runs this and only looks at the exit code.
# Starts permissive because the repository has no code yet; each task that adds
# behaviour is expected to tighten it.
set -eu

if [ -d app ]; then
  python -m compileall -q app > /dev/null
  echo "compile: ok"
fi

if [ -f tests ] || [ -d tests ]; then
  if ls tests/test_*.py > /dev/null 2>&1; then
    python -m pytest -q tests
  fi
fi

echo "check: ok"
