"""Start the whole Sahayak demo with one command.

    python run_demo.py              start the MCP server and the Alexa+ simulator, then open the browser
    python run_demo.py --fresh      same, after deleting the saved demo data so you start from an empty state
    python run_demo.py --no-browser don't open a browser window

Press Ctrl+C to stop both. Needs the packages in requirements.txt and nothing else: no accounts, keys or hardware.
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HOST = "127.0.0.1"  # not "localhost": on Windows that can add ~280 ms per connection while IPv6 is tried first
READY_TIMEOUT_S = 30


def port_is_free(port: int, host: str = HOST) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE if hasattr(socket, "SO_EXCLUSIVEADDRUSE") else socket.SO_REUSEADDR, 1)
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False


def missing_packages() -> list[str]:
    missing = []
    for module, package in (("mcp", 'mcp<2'), ("uvicorn", "uvicorn"), ("starlette", "starlette")):
        try:
            __import__(module)
        except ImportError:
            missing.append(package)
    return missing


def delete_saved_data(db_path: str) -> str:
    """Delete the demo database so the demo starts empty. Only ever removes a '.db' file."""
    path = Path(db_path).resolve()
    if path.suffix != ".db":
        return f"not deleting {path.name}: only .db files are removed"
    if not path.exists():
        return "no saved data to delete: already a clean start"
    path.unlink()
    return f"deleted saved data ({path.name})"


def mcp_is_ready(port: int) -> bool:
    """A real MCP initialize round trip, not just an open port."""
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                       "params": {"protocolVersion": "2025-11-25", "capabilities": {},
                                  "clientInfo": {"name": "run_demo", "version": "1"}}}).encode()
    req = urllib.request.Request(f"http://{HOST}:{port}/mcp", body, {
        "Content-Type": "application/json", "Accept": "application/json, text/event-stream"})
    try:
        with urllib.request.urlopen(req, timeout=3) as r:
            return r.status == 200
    except (urllib.error.URLError, OSError):
        return False


def web_is_ready(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://{HOST}:{port}/", timeout=3) as r:
            return r.status == 200
    except (urllib.error.URLError, OSError):
        return False


def tail(path: Path, lines: int = 12) -> str:
    try:
        return "\n".join(path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:])
    except OSError:
        return "(no log)"


def stop(procs: list[subprocess.Popen]) -> None:
    for p in procs:
        if p.poll() is None:
            p.terminate()
    deadline = time.time() + 5
    for p in procs:
        try:
            p.wait(timeout=max(0.1, deadline - time.time()))
        except subprocess.TimeoutExpired:
            p.kill()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Run the Sahayak MCP server and the Alexa+ simulator together.")
    ap.add_argument("--fresh", action="store_true", help="delete the saved demo data first (start from empty)")
    ap.add_argument("--no-browser", action="store_true", help="do not open a browser window")
    ap.add_argument("--port", type=int, default=8000, help="MCP server port (default 8000)")
    ap.add_argument("--web-port", type=int, default=8080, help="simulator port (default 8080)")
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(line_buffering=True)  # show each line at once, even when output is piped or redirected
    args = parse_args(argv)

    if missing := missing_packages():
        print("Some packages are missing: " + ", ".join(missing))
        print('Install them with:  pip install -r requirements.txt   (or: pip install "mcp<2" uvicorn)')
        return 1
    for name, port in (("MCP server", args.port), ("simulator", args.web_port)):
        if not port_is_free(port):
            print(f"Port {port} ({name}) is already in use. Another copy may be running: stop it, or pick other ports "
                  f"with --port and --web-port.")
            return 1

    env = {**os.environ, "SAHAYAK_MCP_URL": f"http://{HOST}:{args.port}/mcp", "PYTHONUNBUFFERED": "1"}
    for var in ("SAHAYAK_ACCESS_TOKEN", "SAHAYAK_MCP_TOKEN", "SAHAYAK_ALLOWED_HOSTS"):
        env.pop(var, None)  # the local demo runs open; a stray hosting setting must not lock the simulator out
    if args.fresh:
        sys.path.insert(0, str(ROOT))
        from core import store
        print(delete_saved_data(os.environ.get("SAHAYAK_DB", store.DB_PATH)))

    logs = Path(tempfile.mkdtemp(prefix="sahayak-logs-"))
    procs: list[subprocess.Popen] = []
    specs = [("MCP server", ["-m", "server.mcp_server"], {"PORT": str(args.port), "HOST": HOST}, logs / "server.log"),
             ("simulator", ["-m", "web.app"], {"WEB_PORT": str(args.web_port)}, logs / "simulator.log")]
    try:
        for name, argv_, extra, log in specs:
            procs.append(subprocess.Popen([sys.executable, *argv_], cwd=ROOT, env={**env, **extra},
                                          stdout=open(log, "wb"), stderr=subprocess.STDOUT))
        print("Starting the MCP server and the simulator...")

        deadline = time.time() + READY_TIMEOUT_S
        ready = {"MCP server": lambda: mcp_is_ready(args.port), "simulator": lambda: web_is_ready(args.web_port)}
        pending = set(ready)
        while pending and time.time() < deadline:
            for (name, _, _, log), proc in zip(specs, procs):
                if proc.poll() is not None:
                    print(f"\nThe {name} stopped while starting (exit code {proc.returncode}). Its last log lines:\n{tail(log)}")
                    return 1
            pending = {n for n in pending if not ready[n]()}
            time.sleep(0.3)
        if pending:
            print(f"\nTimed out waiting for: {', '.join(sorted(pending))}. Logs are in {logs}")
            return 1

        url = f"http://{HOST}:{args.web_port}"
        print(f"\nReady.\n  Simulator:  {url}\n  MCP server: http://{HOST}:{args.port}/mcp   (Streamable HTTP, spec 2025-11-25)")
        print("\nPress Ctrl+C to stop both.")
        if not args.no_browser:
            webbrowser.open(url)

        def _shutdown(*_):
            raise KeyboardInterrupt
        for sig in ("SIGTERM", "SIGBREAK"):  # SIGBREAK is what Ctrl+Break and a console-group stop send on Windows
            if hasattr(signal, sig):
                signal.signal(getattr(signal, sig), _shutdown)

        while all(p.poll() is None for p in procs):
            time.sleep(0.5)
        for (name, _, _, log), proc in zip(specs, procs):
            if proc.poll() is not None:
                print(f"\nThe {name} stopped unexpectedly (exit code {proc.returncode}). Last log lines:\n{tail(log)}")
        return 1
    except KeyboardInterrupt:
        print("\nStopping...")
        return 0
    finally:
        stop(procs)


if __name__ == "__main__":
    sys.exit(main())
