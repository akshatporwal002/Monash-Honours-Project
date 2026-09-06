"""Launcher acceptance with actual disposable Windows child processes."""

import importlib.util
import json
import os
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "task7_launcher", ROOT / "scripts/quantumlearn_launcher.py"
)
launcher = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = launcher
SPEC.loader.exec_module(launcher)
pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows Job Object acceptance")


@pytest.fixture
def endpoint():
    state = {"ready": True, "requests": 0}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            state["requests"] += 1
            body = json.dumps(
                {
                    "status": "ready" if state["ready"] else "not_ready",
                    "checks": {
                        name: "ready" if state["ready"] else "not_ready"
                        for name in launcher.CHECK_NAMES
                    },
                }
            ).encode()
            self.send_response(200 if state["ready"] else 503)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield state, f"http://127.0.0.1:{server.server_port}/ready"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def sleeper():
    return [sys.executable, "-c", "import time; time.sleep(60)"]


def services(command=None):
    return {
        name: (command if name == "worker" and command else sleeper(), ROOT)
        for name in ("api", "worker", "frontend")
    }


def tracked_job(monkeypatch):
    import _winapi

    children = []
    original = launcher.WindowsJob.start

    def start(self, command, cwd):
        child = original(self, command, cwd)
        child.task7_watch = _winapi.OpenProcess(0x00100000, False, child.pid)
        children.append(child)
        return child

    monkeypatch.setattr(launcher.WindowsJob, "start", start)
    return children


def assert_children_exited(children):
    import _winapi

    for child in children:
        try:
            assert _winapi.WaitForSingleObject(child.task7_watch, 3000) == 0
        finally:
            _winapi.CloseHandle(child.task7_watch)


def test_port_conflict_fails_without_disturbing_listener():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]
        with pytest.raises(launcher.LauncherError):
            launcher.check_ports((port,))
        assert listener.getsockname()[1] == port


def test_explicit_stop_kills_only_owned_children(tmp_path, endpoint, monkeypatch):
    state, url = endpoint
    children = tracked_job(monkeypatch)
    stop = tmp_path / "stop"
    outsider = subprocess.Popen(sleeper(), creationflags=subprocess.CREATE_NO_WINDOW)
    timer = threading.Timer(1.0, lambda: stop.touch())
    timer.start()
    try:
        with launcher.WindowsJob() as job:
            launcher.Supervisor(job, stop).run(services(), url, url, 3, no_browser=True)
        assert state["requests"] > 0
        assert len(children) == 3
        assert_children_exited(children)
        assert outsider.poll() is None
    finally:
        timer.cancel()
        outsider.kill()
        outsider.wait(timeout=5)


def test_child_start_failure_cleans_every_owned_process(tmp_path, endpoint, monkeypatch):
    _, url = endpoint
    children = tracked_job(monkeypatch)
    with pytest.raises(launcher.LauncherError), launcher.WindowsJob() as job:
        launcher.Supervisor(job, tmp_path / "stop").run(
            services([sys.executable, "-c", "raise SystemExit(7)"]),
            url,
            url,
            3,
            no_browser=True,
        )
    assert children
    assert_children_exited(children)


def test_unready_timeout_is_bounded_and_cleans_owned_processes(tmp_path, endpoint, monkeypatch):
    state, url = endpoint
    state["ready"] = False
    children = tracked_job(monkeypatch)
    started = time.monotonic()
    with pytest.raises(launcher.LauncherError), launcher.WindowsJob() as job:
        launcher.Supervisor(job, tmp_path / "stop").run(services(), url, url, 0.5, no_browser=True)
    assert time.monotonic() - started < 5
    assert state["requests"] > 0
    assert len(children) == 3
    assert_children_exited(children)


def test_supervisor_death_kills_its_descendant_tree(tmp_path):
    import _winapi

    marker = tmp_path / "grandchild.pid"
    child_code = (
        "import subprocess,sys,time; from pathlib import Path; "
        "p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'],"
        "creationflags=subprocess.CREATE_NO_WINDOW); "
        f"Path({str(marker)!r}).write_text(str(p.pid)); time.sleep(60)"
    )
    supervisor_code = (
        "import sys,time; from pathlib import Path; "
        f"sys.path.insert(0,{str(ROOT / 'scripts')!r}); "
        "from quantumlearn_launcher import WindowsJob; job=WindowsJob(); "
        f"job.start([sys.executable,'-c',{child_code!r}],Path({str(ROOT)!r})); "
        "time.sleep(60)"
    )
    supervisor = subprocess.Popen(
        [sys.executable, "-c", supervisor_code],
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    watch = None
    try:
        deadline = time.monotonic() + 10
        while not marker.exists() and time.monotonic() < deadline:
            assert supervisor.poll() is None
            time.sleep(0.05)
        assert marker.exists()
        watch = _winapi.OpenProcess(0x00100000, False, int(marker.read_text()))
        assert _winapi.WaitForSingleObject(watch, 0) == _winapi.WAIT_TIMEOUT
        supervisor.kill()
        supervisor.wait(timeout=5)
        assert _winapi.WaitForSingleObject(watch, 5000) == 0
    finally:
        if supervisor.poll() is None:
            supervisor.kill()
        supervisor.wait(timeout=5)
        if watch is not None:
            _winapi.CloseHandle(watch)


def test_setup_timeout_terminates_actual_child(tmp_path, monkeypatch):
    children = tracked_job(monkeypatch)
    started = time.monotonic()
    with pytest.raises(launcher.LauncherError), launcher.WindowsJob() as job:
        launcher.prepare(job, sleeper(), ROOT, "test setup", started + 0.3, tmp_path / "stop")
    assert time.monotonic() - started < 3
    assert len(children) == 1
    assert_children_exited(children)


def test_slow_response_cannot_extend_probe_deadline():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Length", "100")
            self.end_headers()
            # Each byte arrives before a socket read timeout, but the whole read runs longer.
            try:
                for _ in range(20):
                    self.wfile.write(b" ")
                    self.wfile.flush()
                    time.sleep(0.05)
            except OSError:
                pass

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        started = time.monotonic()
        ready, _ = launcher.probe_url(
            f"http://127.0.0.1:{server.server_port}/ready", 0.2, readiness=True
        )
        assert not ready
        assert time.monotonic() - started < 0.8
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
