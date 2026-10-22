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

from agents.router import _NUM, MIN_MONTHLY, Route, _to_amount, route

MCP_URL = os.environ.get("SAHAYAK_MCP_URL", "http://127.0.0.1:8000/mcp")
HERE = Path(__file__).parent


class Turn:
    """One in-flight tool call, possibly paused waiting for the user to answer a follow-up."""

    def __init__(self) -> None:
        self.question: asyncio.Queue = asyncio.Queue()
        self.answer: asyncio.Future | None = None
        self.task: asyncio.Task | None = None
        self.tool = ""
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

    async with streamablehttp_client(MCP_URL) as (read, write, _):
        async with ClientSession(read, write, elicitation_callback=on_elicit) as session:
            await session.initialize()
            started = time.perf_counter()
            result = await session.call_tool(tool, {**args, "user_id": user_id})
            turn.server_ms = max((time.perf_counter() - started - turn.waited) * 1000, 0.0)
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
    if r.partial:
        pending.update(r.partial)
    elif r.tool is None and pending and (m := re.search(_NUM, text, re.I)):
        value = _to_amount(m.group(1), m.group(2))
        if value < MIN_MONTHLY:
            return Route(None, note="That sounds low for a monthly amount. Please say the full number.")
        pending["monthly_expenses" if "monthly_income" in pending else "monthly_income"] = value
    else:
        if r.tool is not None:
            state.pop("budget", None)  # the user moved on
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
    text = (body.get("text") or "").strip()
    user_id = body.get("user", "demo")
    turn = TURNS.get(sid)

    if turn and turn.answer and not turn.answer.done():
        turn.answer.set_result(text)  # the user is answering the server's follow-up question
    else:
        r = remember_budget(CONV.setdefault(body.get("conv") or sid, {}), route(text), text)
        if r.tool is None:
            return JSONResponse({"session": sid, "speech": r.note, "card": None})
        turn = TURNS[sid] = Turn()
        turn.tool, turn.args = r.tool, r.args
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
    return JSONResponse({"session": sid, "speech": data.get("speech", ""), "card": {"tool": turn.tool, **data},
                         "trace": turn.trace()})


async def index(_request):
    return FileResponse(HERE / "index.html")


app = Starlette(routes=[HttpRoute("/", index), HttpRoute("/api/chat", chat, methods=["POST"])])

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("WEB_PORT", "8080")))
