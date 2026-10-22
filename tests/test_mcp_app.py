"""The MCP Apps contract the server must honour, checked in-process (no network, no running server)."""
import asyncio
import re
from pathlib import Path

from server.mcp_server import UI_MIME, UI_URI, mcp

CARD = Path(__file__).resolve().parent.parent / "server" / "ui" / "card.html"


def test_every_tool_declares_its_screen_under_the_current_and_the_legacy_key():
    tools = asyncio.run(mcp.list_tools())
    assert len(tools) >= 8
    for t in tools:
        meta = t.meta or {}
        assert meta.get("ui", {}).get("resourceUri") == UI_URI, t.name   # current key
        assert meta.get("ui/resourceUri") == UI_URI, t.name              # deprecated key, for older hosts


def test_the_screen_is_a_ui_resource_with_the_mcp_apps_mime_type():
    resources = asyncio.run(mcp.list_resources())
    ui = [r for r in resources if str(r.uri) == UI_URI]
    assert len(ui) == 1 and ui[0].mimeType == UI_MIME == "text/html;profile=mcp-app"


def test_reading_the_resource_returns_the_view_html():
    contents = list(asyncio.run(mcp.read_resource(UI_URI)))
    assert contents and "ui/initialize" in contents[0].content


def test_view_is_self_contained_so_the_default_csp_is_enough():
    html = CARD.read_text(encoding="utf-8")
    assert not re.search(r"https?://", html), "the view must not load or call anything external"
    assert "<script src" not in html and "fetch(" not in html and "XMLHttpRequest" not in html


def test_view_speaks_the_host_protocol():
    html = CARD.read_text(encoding="utf-8")
    for needed in ("ui/initialize", "ui/notifications/initialized", "ui/notifications/tool-result",
                   "ui/notifications/size-changed", "ui/resource-teardown", "parent.postMessage"):
        assert needed in html, needed


def test_view_only_trusts_messages_from_its_host():
    assert "ev.source !== parent" in CARD.read_text(encoding="utf-8")


def test_view_escapes_text_before_putting_it_in_the_page():
    html = CARD.read_text(encoding="utf-8")
    # every place that builds markup from a loan label, lesson text, question or reason goes through esc()
    for field in ("l.lender_label", "q)", "r)", "d.lesson.title"):
        assert re.search(r"esc\([^)]*" + re.escape(field.rstrip(")")), html), field
