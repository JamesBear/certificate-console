#!/usr/bin/env python3
"""Single entrypoint: start the API and the web app together.

    python run.py            # uvicorn on :8000 + Vite on :5173 (proxying /api)
    python run.py --prod     # build the SPA once, serve everything from uvicorn on :8000

First run creates `.venv`, installs the backend requirements and the frontend
dependencies. Ctrl+C stops both children; if either one dies, the other is stopped.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"
FRONTEND = ROOT / "frontend"
REQUIREMENTS = ROOT / "requirements.txt"
STAMP = VENV / ".installed"


def venv_python() -> Path:
    return VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def in_venv() -> bool:
    return Path(sys.prefix).resolve() == VENV.resolve()


def bootstrap() -> None:
    if not venv_python().exists():
        print("[run] creating .venv", flush=True)
        subprocess.run([sys.executable, "-m", "venv", str(VENV)], check=True)

    if not STAMP.exists() or REQUIREMENTS.stat().st_mtime > STAMP.stat().st_mtime:
        print("[run] installing backend requirements", flush=True)
        subprocess.run(
            [str(venv_python()), "-m", "pip", "install", "--disable-pip-version-check", "-q", "-r", str(REQUIREMENTS)],
            check=True,
        )
        STAMP.write_text("ok", encoding="utf-8")

    if not (FRONTEND / "node_modules").exists():
        print("[run] installing frontend dependencies", flush=True)
        package_manager = shutil.which("pnpm") or shutil.which("npm")
        if package_manager is None:
            raise SystemExit("Node 20+ with pnpm or npm is required to run the web app.")
        subprocess.run([package_manager, "install"], cwd=FRONTEND, check=True)

    if not in_venv():
        os.execv(str(venv_python()), [str(venv_python()), str(Path(__file__)), *sys.argv[1:]])


def pipe(stream, prefix: str) -> None:
    for line in iter(stream.readline, b""):
        print(f"[{prefix}] {line.decode(errors='replace').rstrip()}", flush=True)
    stream.close()


def spawn(args: list[str], cwd: Path, prefix: str) -> subprocess.Popen:
    process = subprocess.Popen(args, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    threading.Thread(target=pipe, args=(process.stdout, prefix), daemon=True).start()
    return process


def build_web() -> None:
    package_manager = shutil.which("pnpm") or shutil.which("npm")
    if package_manager is None:
        raise SystemExit("Node 20+ with pnpm or npm is required to build the web app.")
    print("[run] building the web app", flush=True)
    subprocess.run([package_manager, "run", "build"], cwd=FRONTEND, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the certificate console.")
    parser.add_argument("--prod", action="store_true", help="build the SPA and serve it from FastAPI on one port")
    parser.add_argument("--port", type=int, default=8000, help="API port (default 8000)")
    parser.add_argument("--no-reload", action="store_true", help="disable uvicorn auto-reload")
    args = parser.parse_args()

    bootstrap()

    if args.prod:
        build_web()
        children = [spawn([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(args.port)], ROOT, "api")]
    else:
        reload_flag = [] if args.no_reload else ["--reload"]
        children = [
            spawn([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(args.port), *reload_flag], ROOT, "api"),
            spawn(["npm", "run", "dev"], FRONTEND, "web"),
        ]

    print(f"[run] api  http://127.0.0.1:{args.port}", flush=True)
    if not args.prod:
        print("[run] web  http://127.0.0.1:5173", flush=True)
    print("[run] Ctrl+C to stop", flush=True)

    try:
        while True:
            for child in children:
                code = child.poll()
                if code is not None:
                    print(f"[run] a child exited with {code}; stopping the rest", flush=True)
                    return code
            time.sleep(0.4)
    except KeyboardInterrupt:
        return 0
    finally:
        for child in children:
            child.terminate()
        deadline = time.time() + 5
        for child in children:
            while child.poll() is None and time.time() < deadline:
                time.sleep(0.1)
            if child.poll() is None:
                child.kill()


if __name__ == "__main__":
    raise SystemExit(main())
