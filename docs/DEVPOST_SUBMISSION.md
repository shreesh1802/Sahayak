# Devpost submission draft

Copy each section into the matching field. Items in [brackets] are for you to fill in.

## Tracks and mini challenges
- **Primary track:** Alexa+
- **Mini challenges:** none claimed.
  - *AWS Builder:* not claimed. No AWS service is used in the submitted code.
  - *Open Source:* not claimed separately. The repo is public under the MIT license, but the challenge asks for an
    additional contribution alongside the primary submission. Only claim it if you open a real PR to a public repo
    before the deadline.

## Project name
Sahayak

## Tagline
A voice-first money coach for first-time borrowers, built as an Alexa+ add-on.

## Text description

**The problem.** Many first-time borrowers sign loans they do not understand. "12% flat" sounds like 12% but can cost
about 21% a year. Upfront fees mean you receive less cash than you repay. The monthly payment is often the only number
anyone mentions. These are the people least likely to have a financial adviser, and most likely to prefer a spoken
conversation over a spreadsheet.

**What Sahayak does.** Sahayak is an Alexa+ add-on, built as a self-hosted MCP server. You describe a loan in plain
words and it explains the monthly payment, the total you repay, the cash you actually receive and the true yearly
cost. If you did not say whether the rate is flat or on a reducing balance, the server asks, using MCP elicitation.
It remembers your income and spending, checks whether a payment is realistic, tracks your loans and repayments across
conversations, and teaches one short money lesson at a time.

**How it works.** The server (Python, official MCP SDK) speaks Streamable HTTP and negotiates MCP spec 2025-11-25.
It exposes eight tools and one resource. One of them, `review_loan_offer`, answers "should I take this loan?" by
running a small multi-agent pipeline behind a single tool call: a supervisor plans and re-plans which specialists to
run (a loan analyst, an affordability agent that is skipped when the budget is unknown, and a coach that picks
questions to ask the lender and a lesson from the findings), and a verifier then checks that every number in the
spoken answer traces to the calculator, rejecting and replacing any draft that does not. The agents are rule-based
code, not language models: what is real is the orchestration and the verifier, which sit behind plain interfaces so
a model could be dropped in later. All numbers come from a deterministic calculator that computes flat versus
reducing interest, upfront fees and the true yearly rate (an IRR solved numerically). No language model touches a
figure, so a spoken number can always be traced to the calculator. State lives in SQLite. A simulated Alexa+
experience (an Echo Showâ€“style screen with voice input and cards) acts as the MCP client, so it exercises the real
server over the real protocol.

**Quality checks.** 54 unit tests cover the loan maths, the intent router, and the multi-agent pipeline (including a
test that a composer inventing a number is rejected by the verifier). 21 end-to-end checks run a real MCP
client against the live server, covering the elicitation round trip, input validation, a guard that stops one user
logging repayments on another user's loan, and the Alexa+ latency budget (under 500 ms; measured about 8 ms per call).

**Why it could reach real users.** Alexa+ has no coverage for financial literacy, and a voice-first explainer suits
people who are not comfortable with forms and tables. The same server could be exposed to account-linked users.

**Honest limits.** It is tested against my simulator, not a real Alexa+ device. The language understanding is
rule-based, and explanations are templates. Authentication uses a demo user: production would derive the user from the
OAuth token Alexa+ sends. Sahayak gives education, not regulated financial advice, and states that in its answers.

## Built with
Python, MCP Python SDK (`mcp<2`), Starlette and uvicorn, SQLite, Web Speech API.

## Links
- Code repository: https://github.com/shreesh1802/Sahayak
- Demo video: [paste your YouTube or Vimeo link]

## If the project existed before the hackathon
Not applicable: built during the submission period.

## Product feedback (required)

**Which tools, APIs and SDKs did you use, and for what?**
- MCP Python SDK (`mcp`) and the MCP Streamable HTTP spec (2025-11-25): the server and the client in my simulator.
- Amazon's Alexa+ MCP Toolkit documentation (quickstart and integration guide): to design for the auth, latency and
  response requirements. I did not run Amazon's own simulator or the `alexa-ai` CLI.
- Amazon Bedrock (Nova Lite): I tried to add a model layer, but the playground returned
  `ValidationException: Operation not allowed` on a new account, so no Bedrock code is part of this submission.

**What worked well?**
- The MCP SDK made a spec-compliant Streamable HTTP server quick to write. Elicitation worked first time and fits
  voice conversations well.
- The 500 ms latency requirement is clearly stated and easy to test for.
- Amazon's guidance on tool-description derivation and example phrases is helpful when it is found.

**What needs work?**
- The hackathon Resources page gives Alexa+ only two links, with no starter repo, unlike Fire TV and Ring. Amazon's
  MCP Toolkit quickstart is not linked from it.
- The auth requirements (RFC 9728 metadata, OAuth 2.1 with PKCE, no Dynamic Client Registration) are heavy for a
  hackathon time box. A dev-mode or a drop-in test auth server would help.
- `pip install mcp` now installs the 2.x line, which renamed `FastMCP` and changed other APIs, breaking most existing
  tutorials. I pinned `mcp<2`.
- AWS: credit codes were exhausted before the deadline, and a brand-new account hit `Operation not allowed` in the
  Bedrock playground with no explanation of what to fix.
- Tool changes only apply after `alexa-ai deploy`, which slows the edit-test loop.

**How was onboarding (zero to hello world)?**
About one hour to a working MCP server, plus about an hour lost to a slow package install on Python 3.14 (flaky
downloads and pip backtracking, documented in the friction log). Alexa+ specifics took longer, because the useful
docs are not linked from the hackathon page.

**Would you build with these again?**
Yes. MCP as the integration surface is a good fit for voice. I would want a starter repo and a test auth server first.

## Friction log (optional, up to a 10% bonus)
Paste the contents of `docs/FRICTION_LOG.md`. Before pasting, **add an entry for the Bedrock error** (see below).

## Optional: feature requests
- **Important:** a dev-mode for Alexa+ account linking, so the simulator can be tested without a full OAuth server.
- **Important:** a minimal "hello world" MCP add-on in the Alexa+ docs that passes all checks.
- **Nice-to-have:** hot reload of tool definitions against the simulator.
- **Nice-to-have:** a clear error message and fix link for Bedrock `Operation not allowed` on new accounts.
