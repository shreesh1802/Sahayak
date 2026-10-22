import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import run_demo

ROOT = Path(__file__).resolve().parent.parent
MCP_PORT, WEB_PORT = 8161, 8162  # unlikely to clash with a copy of the demo you already have running


def test_port_is_free_tracks_a_listening_socket():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    s.listen()
    port = s.getsockname()[1]
    assert run_demo.port_is_free(port) is False
    s.close()
    assert run_demo.port_is_free(port) is True


def test_fresh_deletes_only_a_db_file(tmp_path):
    db = tmp_path / "demo.db"
    db.write_bytes(b"data")
    assert "deleted" in run_demo.delete_saved_data(str(db)) and not db.exists()
    assert "already a clean start" in run_demo.delete_saved_data(str(db))


def test_fresh_refuses_to_delete_anything_that_is_not_a_db(tmp_path):
    precious = tmp_path / "notes.txt"
    precious.write_text("keep me")
    assert "not deleting" in run_demo.delete_saved_data(str(precious))
    assert precious.exists()


def test_defaults_and_flags():
    a = run_demo.parse_args([])
    assert (a.fresh, a.no_browser, a.port, a.web_port) == (False, False, 8000, 8080)
    a = run_demo.parse_args(["--fresh", "--no-browser", "--port", "9000", "--web-port", "9001"])
    assert (a.fresh, a.no_browser, a.port, a.web_port) == (True, True, 9000, 9001)


def test_nothing_is_missing_in_this_environment():
    assert run_demo.missing_packages() == []


def _launch(tmp_path, name, *extra):
    out = tmp_path / f"{name}.txt"
    flags = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {}
    env = {**os.environ, "SAHAYAK_DB": str(tmp_path / "launcher_test.db")}
    p = subprocess.Popen([sys.executable, str(ROOT / "run_demo.py"), "--no-browser", "--port", str(MCP_PORT),
                          "--web-port", str(WEB_PORT), *extra], cwd=ROOT, env=env, stdout=open(out, "wb"),
                         stderr=subprocess.STDOUT, **flags)
    return p, out


def _wait_for(path, text, timeout=45):
    end = time.time() + timeout
    while time.time() < end:
        if path.exists() and text in path.read_text(encoding="utf-8", errors="replace"):
            return True
        time.sleep(0.3)
    return False


def _stop(p):
    p.send_signal(signal.CTRL_BREAK_EVENT if os.name == "nt" else signal.SIGINT)
    try:
        p.wait(timeout=20)
    except subprocess.TimeoutExpired:
        p.kill()
        p.wait()


def test_launcher_starts_both_servers_refuses_a_second_copy_and_stops_cleanly(tmp_path):
    (tmp_path / "launcher_test.db").write_bytes(b"old data")
    first, first_out = _launch(tmp_path, "first", "--fresh")
    try:
        assert _wait_for(first_out, "Ready."), first_out.read_text(errors="replace")
        text = first_out.read_text(encoding="utf-8", errors="replace")
        assert "deleted saved data" in text                    # --fresh wiped the old database
        assert run_demo.mcp_is_ready(MCP_PORT) and run_demo.web_is_ready(WEB_PORT)  # a real MCP initialize and the page

        second, second_out = _launch(tmp_path, "second")        # same ports: must fail politely, not crash or hijack
        assert second.wait(timeout=30) == 1
        assert "already in use" in second_out.read_text(encoding="utf-8", errors="replace")
        assert run_demo.mcp_is_ready(MCP_PORT)                  # the first copy was not disturbed
    finally:
        _stop(first)

    assert "Stopping" in first_out.read_text(encoding="utf-8", errors="replace")
    time.sleep(1)
    assert run_demo.port_is_free(MCP_PORT) and run_demo.port_is_free(WEB_PORT), "servers were left running"
