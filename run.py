#!/usr/bin/env python3
"""Run both services; setup is visible and bounded. Ctrl+C stops owned process trees."""
from __future__ import annotations

import argparse
import os
import shutil
import signal
import socket
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"
FRONTEND = ROOT / "frontend"
REQUIREMENTS = ROOT / "requirements.txt"
STAMP = VENV / ".installed"


def venv_python() -> Path:
    return VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def stop_tree(process: subprocess.Popen) -> None:
    if os.name == "nt":
        # Only the PID we created and its descendants; never kill by image name.
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        if os.name != "nt":
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
        process.wait(timeout=5)


def pipe(stream, prefix: str) -> None:
    try:
        for line in iter(stream.readline, b""):
            print(f"[{prefix}] {line.decode(errors='replace').rstrip()}", flush=True)
    finally:
        stream.close()


def spawn(args: list[str], cwd: Path, prefix: str, env=None) -> subprocess.Popen:
    options = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
    process = subprocess.Popen(args, cwd=cwd, env=env, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, **options)
    threading.Thread(target=pipe, args=(process.stdout, prefix), daemon=True).start()
    return process


def stage(label: str, args: list[str], cwd: Path = ROOT, timeout: int = 180) -> None:
    print(f"[run] {label} (timeout {timeout}s)", flush=True)
    process = spawn(args, cwd, "setup")
    try:
        code = process.wait(timeout=timeout)
        if code:
            raise RuntimeError(f"{label} failed with exit code {code}; see setup output above")
    except (subprocess.TimeoutExpired, KeyboardInterrupt):
        stop_tree(process)
        raise


def package_manager() -> str:
    # Windows CreateProcess cannot resolve bare `npm` to npm.cmd. Resolve it first.
    executable = shutil.which("pnpm") or shutil.which("npm")
    if executable is None:
        raise RuntimeError("Node 20+ with npm or pnpm is required")
    return executable


def bootstrap(timeout: int) -> str:
    python = str(venv_python())
    if not venv_python().exists():
        stage("creating .venv", [sys.executable, "-m", "venv", str(VENV)], timeout=timeout)
    if not STAMP.exists() or REQUIREMENTS.stat().st_mtime > STAMP.stat().st_mtime:
        stage("installing backend requirements", [python, "-m", "pip", "install",
              "--disable-pip-version-check", "--timeout", "15", "--retries", "1",
              "-r", str(REQUIREMENTS)], timeout=timeout)
        STAMP.write_text("ok", encoding="utf-8")
    if not (FRONTEND / "node_modules" / "vite" / "bin" / "vite.js").exists():
        stage("installing frontend dependencies", [package_manager(), "install"], FRONTEND, timeout)
    return python


def ensure_seed(python: str, timeout: int) -> None:
    data = Path(os.environ.get("CERT_CONSOLE_DATA", str(ROOT / "data")))
    control = data / "control.db"
    populated = False
    if control.exists():
        with sqlite3.connect(control) as conn:
            has_table = conn.execute("select 1 from sqlite_master where type='table' and name='tenant'").fetchone()
            populated = bool(has_table and conn.execute("select 1 from tenant limit 1").fetchone())
    if not populated:
        stage("seeding a new demo workspace", [python, "-m", "app.seed", str(data)], timeout=timeout)


def ensure_port_free(port: int) -> None:
    with socket.socket() as sock:
        try:
            sock.bind(("127.0.0.1", port))
        except OSError as exc:
            raise RuntimeError(f"Port {port} is already in use; stop that service or choose another port") from exc


def await_ready(children: list[subprocess.Popen], urls: list[str], timeout: int = 30) -> None:
    pending = set(urls)
    deadline = time.monotonic() + timeout
    while pending and time.monotonic() < deadline:
        if any(p.poll() is not None for p in children):
            raise RuntimeError("A service exited during startup; see its prefixed logs above")
        for url in list(pending):
            try:
                with urllib.request.urlopen(url, timeout=1) as response:
                    if response.status == 200:
                        pending.remove(url)
            except (urllib.error.URLError, TimeoutError, OSError):
                pass
        if pending:
            time.sleep(0.1)
    if pending:
        raise RuntimeError(f"Services did not become ready within {timeout}s: {', '.join(sorted(pending))}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prod", action="store_true")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--web-port", type=int, default=5173)
    parser.add_argument("--no-reload", action="store_true")
    parser.add_argument("--no-bootstrap", action="store_true", help="use the active Python environment and already installed frontend dependencies")
    parser.add_argument("--setup-timeout", type=int, default=180)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535 or not 1 <= args.web_port <= 65535 or args.setup_timeout < 1:
        parser.error("ports must be 1..65535 and setup timeout must be positive")
    children: list[subprocess.Popen] = []
    try:
        ensure_port_free(args.port)
        if not args.prod:
            ensure_port_free(args.web_port)
        python = sys.executable if args.no_bootstrap else bootstrap(args.setup_timeout)
        if args.no_bootstrap:
            print("[run] using the active environment; skipping dependency installation", flush=True)
        ensure_seed(python, args.setup_timeout)
        if args.prod:
            stage("building web app", [package_manager(), "run", "build"], FRONTEND, args.setup_timeout)
        env = {**os.environ, "CERT_CONSOLE_API_URL": f"http://127.0.0.1:{args.port}"}
        api = [python, "-u", "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(args.port)]
        if not args.prod and not args.no_reload:
            api.append("--reload")
        children.append(spawn(api, ROOT, "api", env))
        if not args.prod:
            node = shutil.which("node")
            if node is None:
                raise RuntimeError("Node is required to start Vite")
            children.append(spawn([node, str(FRONTEND / "node_modules/vite/bin/vite.js"), "--host", "127.0.0.1",
                                   "--port", str(args.web_port), "--strictPort"], FRONTEND, "web", env))
        urls = [f"http://127.0.0.1:{args.port}/api/health"]
        if not args.prod:
            urls.append(f"http://127.0.0.1:{args.web_port}/")
        await_ready(children, urls)
        print(f"[run] READY: http://127.0.0.1:{args.port if args.prod else args.web_port}", flush=True)
        print("[run] Services are running. This command stays open; press Ctrl+C to stop both.", flush=True)
        while True:
            for child in children:
                code = child.poll()
                if code is not None:
                    print(f"[run] a service exited with {code}; stopping the rest", flush=True)
                    return code
            time.sleep(0.2)
    except KeyboardInterrupt:
        return 0
    except (RuntimeError, OSError, subprocess.TimeoutExpired) as exc:
        print(f"[run] ERROR: {exc}", file=sys.stderr, flush=True)
        return 1
    finally:
        for child in reversed(children):
            stop_tree(child)


if __name__ == "__main__":
    raise SystemExit(main())
