# Sahayak

**A voice-first money coach for first-time borrowers, built as an Alexa+ add-on (MCP server).**

*Sahayak* means "helper" in Hindi. Many people sign loans they don't fully understand: "12% flat" sounds
like 12%, fees are taken before the cash arrives, and the monthly payment is the only number anyone
mentions. Sahayak explains what a loan really costs, in plain spoken language, checks whether the
payment is realistic, and keeps track of loans and repayments across conversations.

Built for the **Amazon Developer Hackathon 2026, Alexa+ track.**

> Sahayak gives financial *education*, not regulated financial advice. It never recommends specific
> lenders or investments.

## What it does

| Ask | What happens |
|---|---|
| "I was offered 50,000 at 24% for 12 months with a 2,000 fee" | Explains the monthly payment, the total repaid, the cash you actually receive, and the **true yearly cost** (63.4% in this example, not 24%). |
| *(rate type not stated)* | The server asks a follow-up question, "flat or reducing balance?", using MCP elicitation, then continues. |
| "Can I afford 4,500 a month?" | Checks against your saved income, expenses and existing loans, and explains the verdict. |
| "My income is 25k and expenses 14k" | Remembers your budget for next time. |
| "Add a loan called shop credit of 12000 at 18 percent for 12 months reducing" | Saves it so repayments can be tracked. |
| "I paid 2,000 on loan 1" / "Show my loans" | Tracks repayments and what is left. |
| "Teach me something" | Gives the next short money lesson with a quiz question. |

## How it works

```
 Alexa+ (MCP client)  â”€â”€Streamable HTTPâ”€â”€â–¶  Sahayak MCP server
   language, speech,        spec 2025-11-25      tools Â· resources Â· elicitation
   screen rendering                                     â”‚
                                                        â–¼
                                          core/ loan maths Â· SQLite memory
```

- **`server/mcp_server.py`** is the Alexa+ add-on: 8 tools, 1 resource, and elicitation for missing details.
- **`agents/pipeline.py`** is the multi-agent layer behind one tool, `review_loan_offer` ("should I take this loan?").
  Alexa+ makes a single call; behind it a **supervisor** plans and re-plans which specialists to run:
  a **loan analyst** (true cost), an **affordability** agent (skipped if the budget is unknown), and a **coach**
  (questions to ask the lender and a lesson chosen from the findings). A **verifier** then checks that every
  number in the spoken answer traces to the calculator, rejecting and replacing any draft that does not.
- **`core/loan.py`** does all the maths deterministically (flat vs reducing interest, fees, true yearly
  rate via IRR, affordability). **Every number that is spoken comes from this calculator; no language
  model touches the figures.**
- **`core/store.py`** is the memory (SQLite): budget, loans, repayments and lesson progress persist across sessions.
- **`web/`** is a simulated Alexa+ experience: an Echo Showâ€“style screen with voice input, spoken replies and
  cards. It acts as an MCP client, so it exercises the real server over the real protocol.
- **`agents/router.py`** is a rule-based intent router standing in for Alexa+'s own language understanding.

## Run it

Requires Python 3.11+ (developed on 3.14).

```bash
python -m venv .venv
.venv/Scripts/activate        # Windows; use `source .venv/bin/activate` elsewhere
pip install "mcp<2" uvicorn pytest
python -m server.mcp_server   # terminal 1: MCP server on http://127.0.0.1:8000/mcp
python -m web.app             # terminal 2: simulator on  http://127.0.0.1:8080
```

Open http://127.0.0.1:8080 and use the quick-start buttons, type, or tap the microphone.

> `mcp<2` is deliberate: `mcp` 2.x renamed `FastMCP` and changed other APIs. See `docs/FRICTION_LOG.md`.

## Tests

```bash
python -m pytest                 # 33 unit tests: loan maths, intent router, multi-agent pipeline and verifier
python -m eval.smoke             # 21 end-to-end checks against a running server
```

The end-to-end check also verifies the Alexa+ latency budget (under 500 ms; measured about 8 ms per tool call),
input validation, and that one user cannot log repayments on another user's loan.

## Honest limitations

- **The agents are not LLM-driven.** The supervisor's planner, the specialists and the composer are rule-based
  code; what is real is the orchestration (planning and re-planning, chained steps, skipping a step when data is
  missing) and the verifier guard. They sit behind plain function interfaces so a model-backed planner or composer
  can replace them, and the verifier would still re-check every figure. No model has been run against this
  (an attempt to enable Amazon Bedrock on a new account failed; see the friction log). A model-backed
  supervisor/specialist/verifier design is planned, with the calculator as the source of truth for all numbers.
- **Not yet connected to real Alexa+.** Tested with the included simulator, not Amazon's simulator or a device.
- **Authentication is a demo user.** In production the user id comes from the OAuth access token Alexa+ sends
  on every request (the Alexa+ MCP Toolkit requires OAuth 2.1 with PKCE).
- **Affordability thresholds** (loan payments above 40% of income, under a 10% cushion) are stated rules of thumb, not credit advice.
- The simulator is a stand-in; behaviour on real Alexa+ may differ.

## Project layout

```
server/   MCP server (tools, resource, elicitation)
core/     loan maths, memory, narration, lessons
agents/   intent router, multi-agent pipeline (supervisor, specialists, verifier)
web/      simulated Alexa+ experience
eval/     end-to-end smoke test
tests/    unit tests
docs/     friction log
```

## Feedback on the tooling

Notes on onboarding and friction, written as they happened, are in [`docs/FRICTION_LOG.md`](docs/FRICTION_LOG.md).
