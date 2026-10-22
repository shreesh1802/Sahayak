"""Simulated Alexa+ front end.

Plays the role of Alexa+ (the MCP *client*): takes what the user says, picks a tool on the
Sahayak MCP server, calls it over Streamable HTTP, answers the server's follow-up questions
(MCP elicitation) with the user's next message, and returns speech plus a card to render.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import time
import uuid
from pathlib import Path

import uvicorn
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.types import ElicitResult
from starlette.applications import Starlette
from starlette.responses import FileResponse, JSONResponse
from starlette.routing import Route as HttpRoute

from core.narrate import money
from agents.router import (_NUM, MIN_EMI, MIN_MONTHLY, Route, _to_amount, low_note, route, suggest_full,
                           words_to_digits)

MCP_URL = os.environ.get("SAHAYAK_MCP_URL", "http://127.0.0.1:8000/mcp")
# Only needed when the MCP server is run with SAHAYAK_ACCESS_TOKEN (for example behind a public tunnel).
MCP_HEADERS = {"Authorization": f"Bearer {os.environ['SAHAYAK_MCP_TOKEN']}"} if os.environ.get("SAHAYAK_MCP_TOKEN") else None
HERE = Path(__file__).parent


class Turn:
    """One in-flight tool call, possibly paused waiting for the user to answer a follow-up."""

    def __init__(self) -> None:
        self.question: asyncio.Queue = asyncio.Queue()
        self.answer: asyncio.Future | None = None
        self.task: asyncio.Task | None = None
        self.tool = ""
        self.preface = ""  # spoken before the tool's answer, e.g. which saved value was reused
        self.ui: dict | None = None  # the MCP App view fetched from the server's ui:// resource, if the tool has one
        self.tool_content: list = []  # the CallToolResult content array, passed on to the view
        self.args: dict = {}
        self.elicited = False
        self.waited = 0.0  # seconds spent waiting for the user to answer a follow-up question
        self.server_ms = 0.0  # tools/call round trip, excluding connection setup and time waiting for the user

    def trace(self) -> dict:
        """What actually crossed the wire, shown in the UI's behind-the-scenes panel."""
        return {"method": "tools/call", "tool": self.tool, "arguments": self.args,
                "elicited": self.elicited, "server_ms": round(self.server_ms),
                "protocol": "MCP 2025-11-25 over Streamable HTTP"}


TURNS: dict[str, Turn] = {}


def _answer_from_text(schema: dict, text: str) -> dict:
    """Fill the elicitation schema from the user's free-text reply."""
    nums = [_to_amount(m.group(1), m.group(2)) for m in re.finditer(_NUM, text, re.I)]
    out: dict = {}
    for name, spec in schema.get("properties", {}).items():
        if spec.get("type") == "number" and nums:
            out[name] = nums.pop(0)
        elif spec.get("type") == "string":
            low = text.lower()
            out[name] = "flat" if "flat" in low else "reducing" if "reduc" in low else text.strip()
    return out


APPS_MIME = "text/html;profile=mcp-app"


async def _fetch_app_view(session: ClientSession, tool: str) -> dict | None:
    """MCP Apps host step: if the tool declares _meta.ui.resourceUri, read that ui:// resource.

    Returns None (text-only fallback) when the tool has no screen or the resource is not an MCP App view.
    """
    tools = (await session.list_tools()).tools
    meta = next((t.meta for t in tools if t.name == tool), None) or {}
    uri = (meta.get("ui") or {}).get("resourceUri") or meta.get("ui/resourceUri")  # current key, then deprecated flat key
    if not (isinstance(uri, str) and uri.startswith("ui://")):
        return None
    content = (await session.read_resource(uri)).contents[0]
    html = getattr(content, "text", None)
    if content.mimeType != APPS_MIME or not html:
        return None
    return {"resourceUri": uri, "mimeType": content.mimeType, "html": html}


async def _run_tool(turn: Turn, tool: str, args: dict, user_id: str):
    async def on_elicit(_ctx, params):
        loop = asyncio.get_running_loop()
        turn.answer = loop.create_future()
        await turn.question.put({"message": params.message, "schema": params.requestedSchema})
        asked_at = time.perf_counter()
        text = await turn.answer
        turn.waited += time.perf_counter() - asked_at
        content = _answer_from_text(params.requestedSchema, text)
        return ElicitResult(action="accept" if content else "decline", content=content or None)

    async with streamablehttp_client(MCP_URL, headers=MCP_HEADERS) as (read, write, _):
        async with ClientSession(read, write, elicitation_callback=on_elicit) as session:
            await session.initialize()
            started = time.perf_counter()
            result = await session.call_tool(tool, {**args, "user_id": user_id})
            turn.server_ms = max((time.perf_counter() - started - turn.waited) * 1000, 0.0)
            turn.tool_content = [c.model_dump(exclude_none=True) for c in result.content]
            turn.ui = await _fetch_app_view(session, tool)  # MCP Apps: ask the server for this tool's screen
            if result.isError:
                msg = " ".join(getattr(c, "text", "") for c in result.content)
                return {"error": re.sub(r"^Error executing tool \w+:\s*", "", msg)}
            return result.structuredContent or json.loads(result.content[0].text)


CONV: dict[str, dict] = {}  # per-conversation memory between turns (slot filling), keyed by browser id


def remember_budget(state: dict, r: Route, text: str) -> Route:
    """Complete a half-given budget across turns: 'my income is 25000' ... 'and expenses 14000'.

    A bare number after a question for the missing half fills it in; anything else drops the pending question.
    """
    pending = dict(state.get("budget", {}))
    suspect = state.get("suspect")
    heard = words_to_digits(text.lower())  # the browser sometimes writes numbers as words

    # "How much would the monthly payment be?" was asked: a bare number (or a yes/no to a query) answers it.
    if r.ask:
        state.pop("budget", None); state.pop("suspect", None); state.pop("ask_guess", None); state.pop("ask", None)
        if state.get("last_emi"):  # "is the payment affordable?" right after an offer: use that offer's payment
            emi = state["last_emi"]
            return Route("check_affordability", {"new_emi": emi},
                         note=f"Using the {money(emi)} monthly payment from the offer we just looked at. ")
        state["ask"] = r.ask
        return r
    if state.get("ask") and r.tool is None and not (r.partial or r.suspect):
        low = text.lower()
        guess = state.get("ask_guess")
        if guess is not None and re.search(r"\b(yes|yeah|yep|yup|correct|right|ok|okay|sure)\b", low):
            state.pop("ask"); state.pop("ask_guess")
            return Route("check_affordability", {"new_emi": guess})
        if guess is not None and re.search(r"\b(no|nope|nah)\b", low):
            state.pop("ask_guess")
            return Route(None, note="Okay. Please say or type the full monthly payment, for example 4500.")
        if m := re.search(_NUM, heard, re.I):
            value = _to_amount(m.group(1), m.group(2))
            if value < MIN_EMI:
                state["ask_guess"] = suggest_full(value)
                return Route(None, note=f"I heard {value:,.0f} for the monthly payment, which sounds low. "
                                        f"Did you mean {suggest_full(value):,.0f}? Say yes, or say the full amount.")
            state.pop("ask"); state.pop("ask_guess", None)
            return Route("check_affordability", {"new_emi": value})
    elif state.get("ask") and (r.tool is not None or r.partial or r.suspect):
        state.pop("ask"); state.pop("ask_guess", None)  # the user moved on

    # An amount that sounds low was queried ("I heard 8... did you mean 8,000?"): read the reply to that question.
    if suspect and r.tool is None and not r.partial and not r.suspect:
        low = text.lower()
        if re.search(r"\b(yes|yeah|yep|yup|correct|right|ok|okay|sure)\b", low):
            state.pop("suspect")
            r = Route(None, partial={k: (suggest_full(v) if k in suspect["low"] else v)
                                     for k, v in suspect["values"].items()})
        elif re.search(r"\b(no|nope|nah)\b", low):
            state.pop("suspect")
            return Route(None, note="Okay. Please say or type the full amount, for example 8000.")

    if r.suspect:  # too low to be a real monthly amount: ask rather than guess or reject
        state["suspect"] = {"values": r.suspect, "low": [k for k, v in r.suspect.items() if v < MIN_MONTHLY]}
        return r
    if r.partial:
        state.pop("suspect", None)
        pending.update(r.partial)
    elif r.tool is None and pending and (m := re.search(_NUM, heard, re.I)):
        value = _to_amount(m.group(1), m.group(2))
        field_ = "monthly_expenses" if "monthly_income" in pending else "monthly_income"
        if value < MIN_MONTHLY:
            low = {field_: value}
            state["suspect"] = {"values": low, "low": [field_]}
            return Route(None, suspect=low, note=low_note(low))
        pending[field_] = value
    else:
        if r.tool is not None:
            state.pop("budget", None)  # the user moved on
            state.pop("suspect", None)
        return r
    if len(pending) == 2:
        state.pop("budget", None)
        return Route("save_my_budget", pending)
    state["budget"] = pending
    ask = "what are your regular monthly expenses" if "monthly_income" in pending else "what is your monthly income"
    return Route(None, note=f"Thanks. And {ask}?")


async def chat(request):
    body = await request.json()
    sid = body.get("session") or uuid.uuid4().hex
    conv_state = CONV.setdefault(body.get("conv") or sid, {})
    text = (body.get("text") or "").strip()
    user_id = body.get("user", "demo")
    turn = TURNS.get(sid)

    if turn and turn.answer and not turn.answer.done():
        turn.answer.set_result(text)  # the user is answering the server's follow-up question
    else:
        r = remember_budget(conv_state, route(text), text)
        if r.tool is None:
            return JSONResponse({"session": sid, "speech": r.note, "card": None})
        turn = TURNS[sid] = Turn()
        turn.tool, turn.args, turn.preface = r.tool, r.args, r.note
        turn.task = asyncio.create_task(_run_tool(turn, r.tool, r.args, user_id))

    waiter = asyncio.create_task(turn.question.get())
    done, _ = await asyncio.wait({turn.task, waiter}, timeout=20, return_when=asyncio.FIRST_COMPLETED)
    if waiter in done:  # server asked a follow-up question
        q = waiter.result()
        turn.elicited = True
        return JSONResponse({"session": sid, "speech": q["message"], "card": None, "awaiting_reply": True,
                             "trace": {**turn.trace(), "event": "elicitation/create", "asked": q["message"]}})
    waiter.cancel()
    if turn.task not in done:
        return JSONResponse({"session": sid, "speech": "Sorry, that took too long. Please try again.", "card": None})
    TURNS.pop(sid, None)
    try:
        data = turn.task.result()
    except Exception as e:  # surface tool/transport failures as speech, never a stack trace
        return JSONResponse({"session": sid, "speech": f"Sorry, something went wrong: {e}", "card": None})
    if "error" in data:
        return JSONResponse({"session": sid, "speech": f"Sorry: {data['error']}", "card": None,
                             "trace": {**turn.trace(), "event": "tool error"}})
    if isinstance(data.get("cost"), dict) and "emi" in data["cost"]:
        conv_state["last_emi"] = data["cost"]["emi"]  # so "is the payment affordable?" can refer to it
    return JSONResponse({"session": sid, "speech": turn.preface + data.get("speech", ""),
                         "card": {"tool": turn.tool, **data}, "trace": turn.trace(),
                         # what an MCP Apps host needs to show the screen: the view, and the call it belongs to
                         "ui": turn.ui, "tool_input": turn.args,
                         "tool_result": {"content": turn.tool_content, "structuredContent": data}})


async def index(_request):
    return FileResponse(HERE / "index.html")


app = Starlette(routes=[HttpRoute("/", index), HttpRoute("/api/chat", chat, methods=["POST"])])

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("WEB_PORT", "8080")))
