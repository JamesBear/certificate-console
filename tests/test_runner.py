"""Startup must be bounded and clean up services even if launch is only partial."""
import subprocess
import sys

import pytest
import run


def test_setup_timeout_stops_owned_process(monkeypatch):
    spawned = []
    original = run.spawn
    def record(*args, **kwargs):
        child = original(*args, **kwargs)
        spawned.append(child)
        return child
    monkeypatch.setattr(run, "spawn", record)
    with pytest.raises(subprocess.TimeoutExpired):
        run.stage("test stalled installer", [sys.executable, "-c", "import time; time.sleep(30)"], timeout=1)
    assert len(spawned) == 1
    assert spawned[0].poll() is not None


def test_second_service_launch_failure_cleans_up_first(monkeypatch):
    child = object()
    stopped = []
    def launch(args, *rest):
        if "uvicorn" in args:
            return child
        raise OSError("injected Vite launch failure")
    monkeypatch.setattr(sys, "argv", ["run.py", "--no-bootstrap", "--no-reload"])
    monkeypatch.setattr(run, "ensure_port_free", lambda port: None)
    monkeypatch.setattr(run, "ensure_seed", lambda *args: None)
    monkeypatch.setattr(run, "spawn", launch)
    monkeypatch.setattr(run, "stop_tree", stopped.append)
    assert run.main() == 1
    assert stopped == [child]
