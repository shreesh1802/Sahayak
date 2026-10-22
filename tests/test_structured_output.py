"""Every tool must send structuredContent: the MCP App card reads it, and a real host passes the result through as is.

(An earlier version annotated the tools `-> dict`, which this SDK treats as unstructured, so results carried only a JSON
text blob. The simulator parsed that text and hid the problem; a real host would not have.)
"""
import asyncio
import re
from pathlib import Path

from mcp.types import CallToolResult

from server.mcp_server import mcp

CARD = (Path(__file__).resolve().parent.parent / "server" / "ui" / "card.html").read_text(encoding="utf-8")

# Tools that need no elicitation and no prior data, called with safe arguments on a throwaway database.
CALLS = {
    "save_my_budget": {"monthly_income": 25000, "monthly_expenses": 14000, "user_id": "structured-test"},
    "add_loan": {"lender_label": "shop credit", "principal": 12000, "annual_rate": 18, "term_months": 12,
                 "rate_type": "reducing", "user_id": "structured-test"},
    "my_loans": {"user_id": "structured-test"},
    "next_lesson": {"user_id": "structured-test"},
    "explain_loan": {"principal": 50000, "annual_rate": 24, "term_months": 12, "fees": 2000, "rate_type": "flat",
                     "user_id": "structured-test"},
}


def test_every_tool_declares_an_output_schema():
    tools = asyncio.run(mcp.list_tools())
    missing = [t.name for t in tools if not t.outputSchema]
    assert not missing, f"tools without structured output: {missing}"


def test_results_carry_structured_content(tmp_path, monkeypatch):
    monkeypatch.setattr("core.store.DB_PATH", str(tmp_path / "structured.db"))
    for name, args in CALLS.items():
        result = asyncio.run(mcp.call_tool(name, args))
        content, structured = result if isinstance(result, tuple) else (result, None)
        assert isinstance(structured, dict) and structured, f"{name} returned no structuredContent"
        assert "speech" in structured, f"{name}: the spoken answer should be part of the structured result"


def test_the_card_can_fall_back_to_the_text_version_of_a_result():
    assert "function dataOf(result)" in CARD
    assert re.search(r"JSON\.parse\(items\[i\]\.text\)", CARD)
    assert "d = dataOf(result)" in CARD
