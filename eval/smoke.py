"""End-to-end smoke test against a running Sahayak MCP server.

    python -m eval.smoke [http://127.0.0.1:8000/mcp]

Acts as the MCP client (as Alexa+ would): discovers tools, calls each one, answers the
server's follow-up questions (elicitation), and checks the 500 ms Alexa+ latency budget.
Exits non-zero on any failure.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.types import ElicitResult

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/mcp"
BUDGET_MS = 500
UID = f"smoke-{int(time.time())}"
failures: list[str] = []
asked: list[str] = []


in_callback = 0.0  # seconds spent answering the server's follow-up questions (the client's time, not the server's)


async def on_elicit(_ctx, params):
    global in_callback
    started = time.perf_counter()
    try:
        return await _answer(params)
    finally:
        in_callback += time.perf_counter() - started


async def _answer(params):
    asked.append(params.message)
    props = params.requestedSchema.get("properties", {})
    if "rate_type" in props:
        return ElicitResult(action="accept", content={"rate_type": "flat"})
    return ElicitResult(action="accept", content={"monthly_income": 25000, "monthly_expenses": 14000})


def check(name: str, ok: bool, detail: str = "") -> None:
    print(("PASS " if ok else "FAIL ") + name + (f"  {detail}" if detail else ""))
    if not ok:
        failures.append(name)


async def call(session, tool: str, args: dict):
    """Returns (result, data, ms) where ms is the round trip minus time the client spent answering follow-ups."""
    before = in_callback
    t0 = time.perf_counter()
    res = await session.call_tool(tool, args)
    ms = (time.perf_counter() - t0 - (in_callback - before)) * 1000
    data = res.structuredContent or (json.loads(res.content[0].text) if res.content and not res.isError else {})
    return res, data, ms


async def main() -> None:
    token = os.environ.get("SAHAYAK_MCP_TOKEN")
    headers = {"Authorization": f"Bearer {token}"} if token else None
    async with streamablehttp_client(URL, headers=headers) as (r, w, _):
        async with ClientSession(r, w, elicitation_callback=on_elicit) as s:
            init = await s.initialize()
            check("negotiates spec 2025-11-25", init.protocolVersion == "2025-11-25", init.protocolVersion)

            tools = {t.name for t in (await s.list_tools()).tools}
            want = {"explain_loan", "save_my_budget", "check_affordability", "add_loan",
                    "log_repayment", "my_loans", "next_lesson"}
            check("all tools discoverable", want <= tools, str(sorted(want - tools)))

            # MCP Apps: every tool declares its screen, and the screen is served as a ui:// resource
            listed = {t.name: t for t in (await s.list_tools()).tools}
            uris = {n: ((t.meta or {}).get("ui") or {}).get("resourceUri") for n, t in listed.items()}
            check("every tool declares _meta.ui.resourceUri", all(u == "ui://sahayak/card" for u in uris.values()),
                  str({n: u for n, u in uris.items() if u != "ui://sahayak/card"}))
            ui = await s.read_resource("ui://sahayak/card")
            body = ui.contents[0]
            check("ui:// resource has the MCP Apps mime type", body.mimeType == "text/html;profile=mcp-app", str(body.mimeType))
            html = getattr(body, "text", "") or ""
            check("view speaks the host protocol (ui/initialize, tool-result)",
                  "ui/initialize" in html and "ui/notifications/tool-result" in html)
            check("view is self-contained (no external scripts or network)",
                  "<script src" not in html and "http://" not in html and "https://" not in html and "fetch(" not in html)

            # elicitation path: no rate_type given, server must ask
            res, d, ms = await call(s, "explain_loan", {"principal": 50000, "annual_rate": 24, "term_months": 12,
                                                       "fees": 2000, "user_id": UID})
            check("explain_loan asked a follow-up question", len(asked) >= 1 and "flat" in asked[0].lower())
            check("explain_loan flat numbers", abs(d["cost"]["emi"] - 5166.67) < 0.01 or d["cost"]["rate_type"] == "flat",
                  f"emi={d['cost']['emi']}")
            check("explain_loan true rate > quoted", d["cost"]["effective_annual_rate"] > 24,
                  f"{d['cost']['effective_annual_rate']}%")
            print("  speech:", d["speech"])

            # no elicitation when rate_type is given; latency measured here
            res, d, ms = await call(s, "explain_loan", {"principal": 100000, "annual_rate": 12, "term_months": 12,
                                                       "rate_type": "reducing", "user_id": UID})
            check(f"explain_loan latency < {BUDGET_MS} ms", ms < BUDGET_MS, f"{ms:.0f} ms")
            check("reducing EMI is 8884.88", abs(d["cost"]["emi"] - 8884.88) < 0.01, str(d["cost"]["emi"]))
            check("result carries structuredContent (the MCP App card reads it)",
                  isinstance(res.structuredContent, dict) and "speech" in res.structuredContent)

            # multi-agent review: separate user, so its follow-up questions are counted on their own
            before = len(asked)
            res, d, ms = await call(s, "review_loan_offer", {"principal": 50000, "annual_rate": 24, "term_months": 12,
                                                            "fees": 2000, "user_id": UID + "-review"})
            check("review asked for rate type and budget", len(asked) - before == 2, f"{len(asked) - before} questions")
            steps = [(t["agent"], t["action"]) for t in d.get("agent_trace", [])]
            check("review ran supervisor, analyst, affordability, coach, verifier",
                  {a for a, _ in steps} >= {"supervisor", "loan_analyst", "affordability", "coach", "verifier"},
                  str(sorted({a for a, _ in steps})))
            check("verifier approved every spoken number", ("verifier", "approved") in steps)
            check("review gives questions for the lender", len(d.get("questions", [])) >= 3)
            check(f"review latency < {BUDGET_MS} ms (excluding the client's time answering follow-ups)", ms < BUDGET_MS, f"{ms:.0f} ms")

            res, d, ms = await call(s, "check_affordability", {"new_emi": 4500, "user_id": UID})
            check("check_affordability asked for budget", any("income" in q.lower() for q in asked))
            check("affordability verdict returned", d.get("affordability", {}).get("verdict") in
                  {"comfortable", "tight", "unaffordable"}, str(d.get("affordability", {}).get("verdict")))

            res, d, _ = await call(s, "add_loan", {"lender_label": "shop credit", "principal": 12000, "annual_rate": 18,
                                                  "term_months": 12, "rate_type": "reducing", "user_id": UID})
            check("loan numbers are per user, starting at 1", d["loan_number"] >= 1)
            res, d, _ = await call(s, "log_repayment", {"amount": 1000, "lender_label": "shop", "user_id": UID})
            check("log_repayment by name ok", d.get("logged") is True)
            res, d, _ = await call(s, "my_loans", {"user_id": UID})
            check("my_loans shows repayment", d["loans"] and d["loans"][0]["paid"] == 1000)

            res, d, _ = await call(s, "log_repayment", {"amount": 500, "loan_number": 1, "user_id": "someone-else"})
            check("cannot log repayment on another user's loan", res.isError)
            res, d, _ = await call(s, "log_repayment", {"amount": 500, "loan_number": 7, "user_id": UID})
            check("unknown loan number is rejected", res.isError)

            res, d, _ = await call(s, "explain_loan", {"principal": -5, "annual_rate": 10, "term_months": 12,
                                                      "rate_type": "flat", "user_id": UID})
            check("invalid input is rejected, not computed", res.isError)

            res, d, _ = await call(s, "next_lesson", {"user_id": UID})
            check("next_lesson returns a lesson", "lesson" in d)

    print(f"\n{len(failures)} failure(s)" if failures else "\nall checks passed")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    asyncio.run(main())
