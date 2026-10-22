#!/usr/bin/env python3
"""Single entrypoint: start the API and the web app together.

    python run.py             # uvicorn on :8000 + Vite on :5173 (proxying /api)
    python run.py --prod      # build the SPA once and serve everything from uvicorn
    python run.py --port 8010 --no-reload
    python run.py --seed      # recreate the demo data first

Installs what it needs on first run. Ctrl+C stops both children; if either one dies, the other is
stopped too. Deliberately does not create a virtualenv: the `python` you invoked is the one used, and
missing packages are installed into it - one moving part instead of three.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FRONTEND = ROOT / "frontend"
REQUIREMENTS = ROOT / "requirements.txt"
VITE_ENTRY = FRONTEND / "node_modules" / "vite" / "bin" / "vite.js"
DIST_INDEX = FRONTEND / "dist" / "index.html"


def say(message: str) -> None:
    print(f"[run] {message}", flush=True)


def ensure_backend() -> None:
    missing = [name for name in ("fastapi", "uvicorn") if importlib.util.find_spec(name) is None]
    if not missing:
        return
    say(f"installing backend dependencies ({', '.join(missing)})")
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "-q", "-r", str(REQUIREMENTS)],
        check=True,
    )


def package_manager() -> str | None:
    for candidate in ("npm.cmd", "npm", "pnpm.cmd", "pnpm"):
        found = shutil.which(candidate)
        if found:
            return found
    return None


def node_binary() -> str:
    found = shutil.which("node")
    if found is None:
        raise SystemExit("Node 20+ is required for the web app and was not found on PATH.")
    return found


def run_shim(args: list[str], cwd: Path) -> None:
    """npm and pnpm are .cmd shims on Windows; CreateProcess cannot execute those directly."""
    command = args
    if os.name == "nt":
        command = [os.environ.get("COMSPEC", "cmd.exe"), "/c", *args]
    subprocess.run(command, cwd=cwd, check=True)


def ensure_frontend() -> None:
    if VITE_ENTRY.exists():
        return
    manager = package_manager()
    if manager is None:
        raise SystemExit(
            "frontend/node_modules is missing and neither npm nor pnpm is on PATH.\n"
            "Install Node 20+ and run:  cd frontend && npm install"
        )
    say(f"installing frontend dependencies with {Path(manager).name}")
    run_shim([manager, "install"], FRONTEND)


def build_frontend() -> None:
    ensure_frontend()
    say("building the web app")
    subprocess.run([node_binary(), str(VITE_ENTRY), "build"], cwd=FRONTEND, check=True)


def pipe(stream, prefix: str) -> None:
    for line in iter(stream.readline, b""):
        print(f"[{prefix}] {line.decode(errors='replace').rstrip()}", flush=True)
    stream.close()


def spawn(args: list[str], prefix: str, cwd: Path = ROOT) -> subprocess.Popen:
    process = subprocess.Popen(args, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    assert process.stdout is not None
    threading.Thread(target=pipe, args=(process.stdout, prefix), daemon=True).start()
    return process


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the certificate console.")
    parser.add_argument("--prod", action="store_true", help="build the SPA and serve it from the API on one port")
    parser.add_argument("--port", type=int, default=8000, help="API port (default 8000)")
    parser.add_argument("--web-port", type=int, default=5173, help="Vite port (default 5173)")
    parser.add_argument("--no-reload", action="store_true", help="disable uvicorn auto-reload")
    parser.add_argument("--seed", action="store_true", help="recreate the demo data before starting")
    args = parser.parse_args()

    ensure_backend()
    ensure_frontend()

    if args.seed:
        say("seeding demo data")
        subprocess.run([sys.executable, "-m", "app.seed", str(ROOT / "data")], cwd=ROOT, check=True)

    children: list[subprocess.Popen] = []

    if args.prod:
        build_frontend()
        if not DIST_INDEX.exists():
            raise SystemExit("the SPA build did not produce frontend/dist/index.html")
        children.append(
            spawn(
                [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(args.port)],
                "api",
            )
        )
        say(f"console  http://127.0.0.1:{args.port}  (API + built SPA)")
    else:
        reload_args = [] if args.no_reload else ["--reload"]
        children.append(
            spawn(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "app.main:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(args.port),
                    *reload_args,
                ],
                "api",
            )
        )
        children.append(
            spawn([node_binary(), str(VITE_ENTRY), "--port", str(args.web_port)], "web", FRONTEND)
        )
        say(f"api      http://127.0.0.1:{args.port}")
        say(f"web      http://127.0.0.1:{args.web_port}")

    say("Ctrl+C to stop")
    try:
        while True:
            for child in children:
                code = child.poll()
                if code is not None:
                    say(f"a child exited with {code}; stopping the rest")
                    return code
            time.sleep(0.4)
    except KeyboardInterrupt:
        return 0
    finally:
        for child in children:
            if child.poll() is None:
                child.terminate()
        deadline = time.time() + 5
        for child in children:
            while child.poll() is None and time.time() < deadline:
                time.sleep(0.1)
            if child.poll() is None:
                child.kill()


if __name__ == "__main__":
    raise SystemExit(main())
