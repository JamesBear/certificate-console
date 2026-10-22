"""Shared first-run bootstrap for native and container startup; never reseed populated data."""
from __future__ import annotations
import os
from contextlib import closing
from pathlib import Path
import sqlite3
import sys
from .seed import seed


def ensure_demo_data(base: str | Path) -> bool:
    base = Path(base).resolve()
    control = base / "control.db"
    if control.exists():
        with closing(sqlite3.connect(control)) as conn:
            table = conn.execute("select 1 from sqlite_master where type='table' and name='tenant'").fetchone()
            if table and conn.execute("select 1 from tenant limit 1").fetchone():
                print(f"Using existing workspace: {base}", flush=True)
                return False
    seed(base)
    print(f"Seeded new demo workspace: {base}", flush=True)
    return True


if __name__ == "__main__":
    ensure_demo_data(sys.argv[1] if len(sys.argv) > 1 else os.environ.get("CERT_CONSOLE_DATA", "data"))
