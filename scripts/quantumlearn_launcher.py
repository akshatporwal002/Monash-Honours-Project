"""Windows local supervisor. Job handles own processes, never PID-based cleanup."""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
import webbrowser
from ctypes import wintypes
from pathlib import Path


class LauncherError(RuntimeError):
    """An operator-safe failure without child output or configuration values."""


class _BasicLimits(ctypes.Structure):
    _fields_ = [
        ("process_time", ctypes.c_longlong),
        ("job_time", ctypes.c_longlong),
        ("flags", wintypes.DWORD),
        ("min_working_set", ctypes.c_size_t),
        ("max_working_set", ctypes.c_size_t),
        ("active_process_limit", wintypes.DWORD),
        ("affinity", ctypes.c_size_t),
        ("priority", wintypes.DWORD),
        ("scheduling", wintypes.DWORD),
    ]


class _ExtendedLimits(ctypes.Structure):
    _fields_ = [
        ("basic", _BasicLimits),
        ("io", ctypes.c_ulonglong * 6),
        ("process_memory", ctypes.c_size_t),
        ("job_memory", ctypes.c_size_t),
        ("peak_process_memory", ctypes.c_size_t),
        ("peak_job_memory", ctypes.c_size_t),
    ]


class Child:
    def __init__(self, handle: int, pid: int):
        self.handle = handle
        self.pid = pid

    def poll(self) -> int | None:
        import _winapi

        if _winapi.WaitForSingleObject(self.handle, 0) == _winapi.WAIT_TIMEOUT:
            return None
        return _winapi.GetExitCodeProcess(self.handle)

    def close(self) -> None:
        import _winapi

        if self.handle:
            _winapi.CloseHandle(self.handle)
            self.handle = 0


class WindowsJob:
    """Assign suspended children before they can spawn descendants.

    Closing the non-inherited handle kills descendants even after a parent exits.
    Windows closes it on supervisor death, including terminal closure.
    """

    def __init__(self):
        if os.name != "nt":
            raise LauncherError("This launcher requires Windows.")
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        signatures = {
            "CreateJobObjectW": ([ctypes.c_void_p, wintypes.LPCWSTR], wintypes.HANDLE),
            "SetInformationJobObject": (
                [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD],
                wintypes.BOOL,
            ),
            "AssignProcessToJobObject": (
                [wintypes.HANDLE, wintypes.HANDLE],
                wintypes.BOOL,
            ),
            "ResumeThread": ([wintypes.HANDLE], wintypes.DWORD),
            "TerminateJobObject": ([wintypes.HANDLE, wintypes.UINT], wintypes.BOOL),
            "CloseHandle": ([wintypes.HANDLE], wintypes.BOOL),
        }
        for name, (arguments, result) in signatures.items():
            function = getattr(self.kernel, name)
            function.argtypes = arguments
            function.restype = result
        self.handle = self.kernel.CreateJobObjectW(None, None)
        self.children: list[Child] = []
        limits = _ExtendedLimits()
        limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self.handle or not self.kernel.SetInformationJobObject(
            self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)
        ):
            self.close()
            raise LauncherError("Windows process ownership setup failed. No services started.")

    def start(self, command: list[str], cwd: Path) -> Child:
        import _winapi
        import msvcrt

        startup = subprocess.STARTUPINFO()
        startup.dwFlags = subprocess.STARTF_USESTDHANDLES | subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = subprocess.SW_HIDE
        # Child diagnostics may contain credentials or provider payloads. Do not retain them.
        with open(os.devnull, "r+b") as sink:
            sink_handle = msvcrt.get_osfhandle(sink.fileno())
            os.set_handle_inheritable(sink_handle, True)
            startup.hStdInput = startup.hStdOutput = startup.hStdError = sink_handle
            startup.lpAttributeList = {"handle_list": [sink_handle]}
            process, thread, pid, _ = _winapi.CreateProcess(
                None,
                subprocess.list2cmdline(command),
                None,
                None,
                True,
                0x4 | subprocess.CREATE_NO_WINDOW,  # CREATE_SUSPENDED
                None,
                str(cwd),
                startup,
            )
        child = Child(process, pid)
        try:
            if not self.kernel.AssignProcessToJobObject(self.handle, process):
                raise LauncherError("Windows refused process ownership. Startup stopped safely.")
            self.children.append(child)
            if self.kernel.ResumeThread(thread) == 0xFFFFFFFF:
                raise LauncherError("Windows could not start an owned helper.")
            return child
        except BaseException:
            _winapi.TerminateProcess(process, 1)
            _winapi.WaitForSingleObject(process, 5000)
            if child not in self.children:
                child.close()
            raise
        finally:
            _winapi.CloseHandle(thread)

    def close(self) -> None:
        import _winapi

        if self.handle:
            self.kernel.TerminateJobObject(self.handle, 1)
            self.kernel.CloseHandle(self.handle)
            self.handle = None
        for child in self.children:
            if child.handle:
                _winapi.WaitForSingleObject(child.handle, 5000)
                child.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def check_ports(ports: tuple[int, ...] = (8000, 5173)) -> None:
    reservations = []
    try:
        for port in ports:
            for family, address in (
                (socket.AF_INET, "0.0.0.0"),
                (socket.AF_INET6, "::"),
            ):
                if family == socket.AF_INET6 and not socket.has_ipv6:
                    continue
                probe = socket.socket(family, socket.SOCK_STREAM)
                reservations.append(probe)
                if family == socket.AF_INET6:
                    probe.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
                probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
                try:
                    probe.bind((address, port))
                except OSError:
                    raise LauncherError(
                        f"Port {port} is unavailable. Stop its owner before retrying."
                    ) from None
    finally:
        for probe in reservations:
            probe.close()


CHECK_NAMES = {
    "database",
    "migrations",
    "worker",
    "pseudonym_secret",
    "production_adapters",
    "llm_credentials",
}


def probe_url(url: str, timeout: float, *, readiness: bool) -> tuple[bool, str]:
    # Socket timeouts apply per read. A slow response must not extend startup forever.
    result = [
        (
            False,
            "readiness endpoint unavailable" if readiness else "frontend unavailable",
        )
    ]
    completed = threading.Event()

    def request() -> None:
        try:
            result[0] = _read_url(url, timeout, readiness=readiness)
        except Exception:  # noqa: BLE001 - untrusted HTTP diagnostics stay private
            result[0] = (False, "HTTP probe unavailable")
        finally:
            completed.set()

    threading.Thread(target=request, daemon=True).start()
    completed.wait(timeout)
    return result[0]


def _read_url(url: str, timeout: float, *, readiness: bool) -> tuple[bool, str]:
    try:
        try:
            response = urllib.request.build_opener(urllib.request.ProxyHandler({})).open(
                url, timeout=timeout
            )
        except urllib.error.HTTPError as error:
            response = error
        with response:
            if not readiness:
                return response.status == 200, "frontend unavailable"
            data = json.loads(response.read(16384))
            checks = data.get("checks", {})
            if not isinstance(checks, dict):
                return False, "invalid readiness response"
            failed = sorted(name for name in CHECK_NAMES if checks.get(name) != "ready")
            ready = response.status == 200 and data.get("status") == "ready" and not failed
            return ready, "readiness checks: " + ", ".join(failed)
    except (OSError, ValueError, AttributeError):
        return (
            False,
            "readiness endpoint unavailable" if readiness else "frontend unavailable",
        )


class Supervisor:
    def __init__(self, job: WindowsJob, stop_file: Path | None):
        self.job = job
        self.stop_file = stop_file

    def stopped(self) -> bool:
        return self.stop_file is not None and self.stop_file.exists()

    def run(
        self,
        services: dict[str, tuple[list[str], Path]],
        ready_url: str,
        frontend_url: str,
        startup_timeout: float,
        no_browser: bool = True,
    ) -> None:
        deadline = time.monotonic() + startup_timeout
        children = {name: self.job.start(command, cwd) for name, (command, cwd) in services.items()}
        ready = False
        detail = "readiness endpoint unavailable"
        while not self.stopped():
            for name, child in children.items():
                code = child.poll()
                if code is not None:
                    hint = {
                        "API": "Check backend settings, migrations, and port 8000.",
                        "Worker": (
                            "Check WORKER_ADAPTER_FACTORY and RESEARCH_ENABLED. "
                            "An existing worker or its fresh heartbeat can block startup; "
                            "wait for the configured stale timeout after a forced stop."
                        ),
                        "Frontend": "Check Node.js 22, frontend dependencies, and port 5173.",
                    }.get(name, "Check configuration and dependencies.")
                    raise LauncherError(f"{name} exited (code {code}). {hint}")
            if not ready:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise LauncherError(f"Startup deadline expired; {detail}.")
                api_ready, detail = probe_url(ready_url, min(1, remaining), readiness=True)
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    continue
                frontend_ready, frontend_detail = probe_url(
                    frontend_url, min(1, remaining), readiness=False
                )
                if not frontend_ready and api_ready:
                    detail = frontend_detail
                ready = api_ready and frontend_ready and time.monotonic() <= deadline
                # A failed bind can exit while an unrelated listener answers probes.
                ready = ready and all(child.poll() is None for child in children.values())
                if ready:
                    print(f"QuantumLearn is ready at {frontend_url}", flush=True)
                    print(
                        "Keep this launcher open. Press Ctrl+C to stop its services.",
                        flush=True,
                    )
                    if not no_browser:
                        webbrowser.open(frontend_url)
            time.sleep(0.1)


def prepare(
    job: WindowsJob,
    command: list[str],
    cwd: Path,
    label: str,
    deadline: float,
    stop_file: Path,
) -> None:
    if stop_file.exists():
        raise KeyboardInterrupt
    if time.monotonic() >= deadline:
        raise LauncherError(f"Setup deadline expired before {label}.")
    print(f"Preparing {label}...", flush=True)
    child = job.start(command, cwd)
    while child.poll() is None:
        if stop_file.exists():
            raise KeyboardInterrupt
        if time.monotonic() >= deadline:
            raise LauncherError(f"Setup deadline expired during {label}.")
        time.sleep(0.1)
    if child.poll() != 0:
        raise LauncherError(
            f"{label} failed (code {child.poll()}). Check installed tools, network access, and backend configuration."
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uv", required=True)
    parser.add_argument("--npm", required=True)
    parser.add_argument("--node", required=True)
    parser.add_argument("--startup-timeout", type=float, default=90)
    parser.add_argument("--setup-timeout", type=float, default=600)
    parser.add_argument("--stop-file", type=Path)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    backend = root / "src-main" / "backend"
    frontend = root / "src-main" / "frontend"
    stop_file = (
        args.stop_file or root / ".scratch" / f"quantumlearn-stop-{uuid.uuid4().hex}"
    ).resolve()
    try:
        if not 0 < args.startup_timeout <= 3600 or not 0 < args.setup_timeout <= 3600:
            raise LauncherError("Timeouts must be between 0 and 3600 seconds.")
        if stop_file.exists():
            raise LauncherError("Stop file already exists. Choose a new stop-file path.")
        if not backend.is_dir() or not frontend.is_dir():
            raise LauncherError("Backend or frontend directory is missing.")
        check_ports()
        stop_file.parent.mkdir(parents=True, exist_ok=True)
        print(f"To stop this run, create this file: {stop_file}", flush=True)
        with WindowsJob() as job:
            deadline = time.monotonic() + args.setup_timeout
            for directory in (backend, frontend):
                if not (directory / ".env").exists():
                    shutil.copyfile(directory / ".env.example", directory / ".env")
            prepare(
                job,
                [args.uv, "sync", "--frozen", "--all-extras"],
                backend,
                "backend dependencies",
                deadline,
                stop_file,
            )
            # Probe emits only a validated path, never Settings or secrets.
            prefix_file = root / ".scratch" / f"quantumlearn-prefix-{uuid.uuid4().hex}.json"
            config_code = (
                "import json,re; from pathlib import Path; from app.core.config import settings; "
                "p=settings.api_prefix; assert re.fullmatch(r'/[A-Za-z0-9/_-]*',p); "
                f"Path({str(prefix_file)!r}).write_text(json.dumps(p))"
            )
            try:
                prefix_file.parent.mkdir(parents=True, exist_ok=True)
                prepare(
                    job,
                    [args.uv, "run", "--frozen", "python", "-c", config_code],
                    backend,
                    "backend settings validation",
                    deadline,
                    stop_file,
                )
                prefix = json.loads(prefix_file.read_text())
            finally:
                prefix_file.unlink(missing_ok=True)
            prepare(
                job,
                [args.uv, "run", "--frozen", "alembic", "upgrade", "head"],
                backend,
                "database migrations",
                deadline,
                stop_file,
            )
            # Execute Node directly so npm.cmd cannot reinterpret workspace paths.
            npm_cli = str(Path(args.npm).parent / "node_modules" / "npm" / "bin" / "npm-cli.js")
            if not (frontend / "node_modules").is_dir():
                prepare(
                    job,
                    [args.node, npm_cli, "ci"],
                    frontend,
                    "frontend dependencies",
                    deadline,
                    stop_file,
                )
            check_ports()
            services = {
                "API": (
                    [
                        args.uv,
                        "run",
                        "--frozen",
                        "uvicorn",
                        "app.main:app",
                        "--host",
                        "127.0.0.1",
                        "--port",
                        "8000",
                        "--no-access-log",
                    ],
                    backend,
                ),
                "Worker": (
                    [args.uv, "run", "--frozen", "quantumlearn-worker"],
                    backend,
                ),
                "Frontend": (
                    [
                        args.node,
                        str(frontend / "node_modules" / "vite" / "bin" / "vite.js"),
                        "--host",
                        "127.0.0.1",
                        "--port",
                        "5173",
                        "--strictPort",
                    ],
                    frontend,
                ),
            }
            Supervisor(job, stop_file).run(
                services,
                f"http://127.0.0.1:8000{prefix.rstrip('/')}/ready",
                "http://localhost:5173",
                args.startup_timeout,
                args.no_browser,
            )
        print("QuantumLearn stopped. Owned services were closed.", flush=True)
        return 0
    except KeyboardInterrupt:
        print("QuantumLearn stopped. Owned services were closed.", flush=True)
        return 0
    except LauncherError as error:
        print(f"QuantumLearn startup failed: {error}", file=sys.stderr, flush=True)
        return 1
    except Exception:  # noqa: BLE001 - the CLI must never expose config/provider exceptions
        print(
            "QuantumLearn launcher failed. Check file access and installed tools. Owned services were closed.",
            file=sys.stderr,
            flush=True,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
