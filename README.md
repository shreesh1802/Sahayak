# Sahayak

**A voice-first money coach for first-time borrowers, built as an Alexa+ add-on (MCP server).**

*Sahayak* means "helper" in Hindi. Many people sign loans they don't fully understand: "12% flat" sounds
like 12%, fees are taken before the cash arrives, and the monthly payment is the only number anyone
mentions. Sahayak explains what a loan really costs, in plain spoken language, checks whether the
payment is realistic, and keeps track of loans and repayments across conversations.

Built for the **Amazon Developer Hackathon 2026, Alexa+ track.**

> Sahayak gives financial *education*, not regulated financial advice. It never recommends specific
> lenders or investments.

## Try it

No accounts, API keys or hardware needed. Python 3.11+ (developed on 3.14).

```bash
git clone https://github.com/shreesh1802/Sahayak.git
cd Sahayak
python -m venv .venv
.venv/Scripts/activate        # Windows; on macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python run_demo.py
```

`run_demo.py` starts the MCP server and the Alexa+ simulator, then opens **http://127.0.0.1:8080**. Click
**Review an offer**, answer the two follow-up questions ("flat", then "my income is 25000 and expenses 14000"), and open
**Behind the scenes** to see the real MCP calls. Press Ctrl+C to stop both.

- `python run_demo.py --fresh` first deletes the saved demo data, so you start from an empty state.
- `python run_demo.py --no-browser` doesn't open a window; `--port` and `--web-port` change the ports.
- Voice input uses your browser's speech recognition (Chrome or Edge); typing and the buttons always work.

## What it does

| Ask | What happens |
|---|---|
| "I was offered 50,000 at 24% for 12 months with a 2,000 fee" | Explains the monthly payment, the total repaid, the cash you actually receive, and the **true yearly cost** (63.4% in this example, not 24%). |
| "Should I take a loan of 50000 at 24 percent for 12 months?" | Runs the multi-agent review: true cost, whether it fits your budget, questions to ask the lender, and a relevant lesson. |
| *(rate type not stated)* | The server asks a follow-up question, "flat or reducing balance?", using MCP elicitation, then continues. |
| "Can I afford 4,500 a month?" | Checks against your saved income, expenses and existing loans, and explains the verdict. |
| "My income is 25k and expenses 14k" | Remembers your budget for next time. |
| "Add a loan called shop credit of 12000 at 18 percent for 12 months reducing" | Saves it so repayments can be tracked. |
| "I paid 2,000 on loan 1" / "Show my loans" | Tracks repayments and what is left. |
| "Teach me something" | Gives the next short money lesson with a quiz question. |

## How it works

```
 Alexa+ (MCP client)  ──Streamable HTTP──▶  Sahayak MCP server
   language, speech,        spec 2025-11-25      tools · resources · elicitation
   hosts the MCP App screen                             │
                                                        ▼
                                          core/ loan maths · SQLite memory
```

- **`server/mcp_server.py`** is the Alexa+ add-on: 8 tools, 2 resources (the user's loans, and the on-screen card),
  and elicitation for missing details.
- **`server/ui/card.html`** is the **MCP App** view: the on-screen card, served by the server as the `ui://sahayak/card`
  resource (`text/html;profile=mcp-app`) and linked from every tool through `_meta.ui.resourceUri`. A host renders it
  in a sandboxed iframe and sends it each tool result over `postMessage`. The view has no network access and escapes
  all text it displays. A host without MCP Apps support just shows the tool's text answer.
- **`agents/pipeline.py`** is the multi-agent layer behind one tool, `review_loan_offer` ("should I take this loan?").
  Alexa+ makes a single call; behind it a **supervisor** plans and re-plans which specialists to run:
  a **loan analyst** (true cost), an **affordability** agent (skipped if the budget is unknown), and a **coach**
  (questions to ask the lender and a lesson chosen from the findings). A **verifier** then checks that every
  number in the spoken answer traces to the calculator, rejecting and replacing any draft that does not.
- **`core/loan.py`** does all the maths deterministically (flat vs reducing interest, fees, true yearly
  rate via IRR, affordability). **Every number that is spoken comes from this calculator; no language
  model touches the figures.**
- **`core/store.py`** is the memory (SQLite): budget, loans, repayments and lesson progress persist across sessions.
- **`web/`** is a simulated Alexa+ experience: voice input, spoken replies and an Echo Show–style screen. It acts as
  an MCP client **and as an MCP Apps host**: it reads each tool's `_meta.ui.resourceUri`, fetches the view from the
  server, mounts it in a sandboxed iframe (`allow-scripts` only, so the view cannot reach the page) and runs the host
  side of the handshake (`ui/initialize`, `ui/notifications/initialized`, then `tool-input` and `tool-result`). The
  "Behind the scenes" panel shows every message. The host is my own implementation of the subset of the protocol
  this app needs; it is not Amazon's.
- **`agents/router.py`** is a rule-based intent router standing in for Alexa+'s own language understanding.

## Running the pieces yourself

`run_demo.py` is a convenience; the two servers are ordinary processes. In two terminals:

```bash
python -m server.mcp_server   # MCP server on http://127.0.0.1:8000/mcp
python -m web.app             # simulator on  http://127.0.0.1:8080
```

> `mcp<2` in `requirements.txt` is deliberate: `mcp` 2.x renamed `FastMCP` and changed other APIs. See `docs/FRICTION_LOG.md`.

## Tests

```bash
python -m pytest                 # 118 unit tests: loan maths, router, agents, verifier, MCP App contract, theme, hardening, launcher
python -m eval.smoke http://127.0.0.1:8000/mcp   # 26 end-to-end checks against a running server
```

The end-to-end check also verifies the Alexa+ latency budget (under 500 ms; typically 9 to 60 ms per tool call here),
the declared screens, that every result carries `structuredContent` (what the MCP App card reads), input validation,
and the multi-agent review. A theme test keeps every text and background colour pair above WCAG contrast. Use `127.0.0.1`, not `localhost`, on Windows:
`localhost` added about 280 ms per connection in testing.

## Public URL

To reach the server from the internet (a tunnel, an access token, and the allowed-host setting the MCP SDK needs), see
[docs/HOSTING.md](docs/HOSTING.md). It also explains why that is a protected demo endpoint and **not** real Alexa+
account linking.

## Honest limitations

- **The agents are not LLM-driven.** The supervisor's planner, the specialists and the composer are rule-based
  code; what is real is the orchestration (planning and re-planning, chained steps, skipping a step when data is
  missing) and the verifier guard. They sit behind plain function interfaces so a model-backed planner or composer
  could replace them, and the verifier would still re-check every figure. No model has been run against this: an
  attempt to enable Amazon Bedrock on a new account failed (see the friction log).
- **Not connected to real Alexa+.** It was tested with the included simulator, not Amazon's simulator or a device.
  In particular the MCP App view has only run in my own host. I built it from the MCP Apps spec (`2026-01-26`),
  which has internal inconsistencies (for example the view's `initialize` field is named `appCapabilities` in the
  text and `capabilities` in the example, so the view sends both), and I have not checked it against Amazon's host.
- **No capability negotiation for MCP Apps.** The spec says hosts advertise `io.modelcontextprotocol/ui` and servers
  should register UI tools only when it is present. The Python MCP SDK (1.x) has no way for a client to send it, so
  the server always declares the screen and relies on the text fallback for hosts that ignore it.
- **Authentication is a demo user.** In production the user id comes from the OAuth access token Alexa+ sends
  on every request (the Alexa+ MCP Toolkit requires OAuth 2.1 with PKCE).
- **Affordability thresholds** (loan payments above 40% of income, under a 10% cushion) are stated rules of thumb,
  not credit advice.
- **English only**, and voice accuracy depends on the browser's speech recognition: a mis-heard amount (for example
  "8" for "8,000") is queried back ("did you mean 8,000?") rather than guessed.

## Project layout

```
run_demo.py   one-command launcher for the whole demo
server/       the MCP server (tools, resources, elicitation) and server/ui/card.html, the MCP App view
core/         loan maths, memory, narration, lessons
agents/       intent router and the multi-agent pipeline (supervisor, specialists, verifier)
web/          the simulated Alexa+ experience and MCP Apps host
eval/         end-to-end smoke test
tests/        unit tests
docs/         friction log and the public-URL guide
```

## Feedback on the tooling

Notes on onboarding and friction, written as they happened, are in [`docs/FRICTION_LOG.md`](docs/FRICTION_LOG.md).

## Licence

MIT. See [LICENSE](LICENSE).
