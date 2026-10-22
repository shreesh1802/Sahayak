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
figure, so a spoken number can always be traced to the calculator. State lives in SQLite.

**The on-screen card is an MCP App.** On Alexa+ devices with a screen, visuals come from the server, not from the
assistant. Sahayak's server serves its card as a `ui://sahayak/card` resource (`text/html;profile=mcp-app`) and
every tool points at it through `_meta.ui.resourceUri`. A host renders that HTML in a sandboxed iframe and passes it
each tool result over `postMessage` (JSON-RPC: `ui/initialize`, `ui/notifications/initialized`, then `tool-input` and
`tool-result`). The view has no network access, only trusts messages from its host, escapes everything it displays,
sizes itself with `size-changed`, and follows the host's light or dark theme. A host without MCP Apps support shows
the tool's plain-text answer instead.

**Simulator.** A simulated Alexa+ experience (voice input, spoken replies, Echo Show–style screen) acts as an MCP
client and as an MCP Apps host: it discovers each tool's view, fetches it from the server, mounts it in a sandboxed
iframe (the view cannot reach the page) and runs the host side of the handshake. A "Behind the scenes" panel shows
every message. The host is my own implementation of the part of the protocol this app needs, not Amazon's.

**Quality checks.** 78 unit tests cover the loan maths, the intent router, the conversation memory, the multi-agent
pipeline (including a test that a composer inventing a number is rejected by the verifier), and the MCP App contract
(every tool declares its screen, the resource has the right MIME type, the view is self-contained and escapes its
text). 25 end-to-end checks run a real MCP client against the live server, covering the elicitation round trip,
the declared screens, input validation, and the Alexa+ latency budget (under 500 ms; measured about 8 to 60 ms per call).

**Why it could reach real users.** Alexa+ has no coverage for financial literacy, and a voice-first explainer suits
people who are not comfortable with forms and tables. The same server could be exposed to account-linked users.

**Honest limits.** It is tested against my simulator, not a real Alexa+ device, and the MCP App view has only run in my
own host, built from the MCP Apps spec; I have not checked it against Amazon's host. The language understanding is
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
- The MCP Apps extension (SEP-1865; spec `2026-01-26` in the ext-apps repository): the on-screen card is an MCP App
  view, and my simulator implements the host side. I used the spec directly, not the `@modelcontextprotocol/ext-apps`
  SDK, because the server is Python.
- Amazon Bedrock (Nova Lite): I tried to add a model layer, but the playground returned
  `ValidationException: Operation not allowed` on a new account, so no Bedrock code is part of this submission.

**What worked well?**
- The MCP SDK made a spec-compliant Streamable HTTP server quick to write. Elicitation worked first time and fits
  voice conversations well.
- The 500 ms latency requirement is clearly stated and easy to test for.
- Amazon's guidance on tool-description derivation and example phrases is helpful when it is found.
- Once found, the MCP Apps spec is clear about the moving parts: a `ui://` resource, a `_meta.ui.resourceUri` link,
  a sandboxed iframe, and a small JSON-RPC handshake. The Python SDK's `FastMCP` already accepts `meta=` on tools and a
  custom `mime_type` on resources, so declaring a view needed no extra library.
- The text-only fallback in the spec makes it safe to ship a screen on hosts that may not render it.

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
- The quickstart suggests a tunnel (`cloudflared`) for local development, but with the Python MCP SDK every request
  through a tunnel fails with `421 Invalid Host header` (its DNS-rebinding protection allows only `localhost`). The fix
  is one setting, `allowed_hosts`, but it is not mentioned anywhere I looked.
- MCP Apps documentation is split: the hackathon page links the API overview, which does not give the metadata keys,
  MIME type or handshake. Those are only in the spec file in the ext-apps repository. The spec also contradicts itself
  in places (the view's `initialize` field is `appCapabilities` in the text and `capabilities` in the example; the
  teardown message is listed as a notification but shown with an `id`; the CSP example conflicts with the stated
  default), so I had to send both field names and tolerate both shapes.
- The spec says hosts advertise `io.modelcontextprotocol/ui` and servers should check it before registering UI tools,
  but the Python MCP SDK (1.x) gives a client no way to send that capability, so the check cannot be done end to end.
- There is no way to test a view against Amazon's host without a developer account; the quickstart mentions a web
  simulator, but nothing on the hackathon page says how to get access.

**How was onboarding (zero to hello world)?**
About one hour to a working MCP server, plus about an hour lost to a slow package install on Python 3.14 (flaky
downloads and pip backtracking, documented in the friction log). Alexa+ specifics took longer, because the useful
docs are not linked from the hackathon page.

**Would you build with these again?**
Yes. MCP as the integration surface is a good fit for voice. I would want a starter repo and a test auth server first.

## Friction log (optional, up to a 10% bonus)
Paste the contents of `docs/FRICTION_LOG.md` (it already includes the Bedrock error and the MCP Apps entries).

## Optional: feature requests
- **Important:** a dev-mode for Alexa+ account linking, so the simulator can be tested without a full OAuth server.
- **Important:** a minimal "hello world" MCP add-on in the Alexa+ docs that passes all checks.
- **Nice-to-have:** hot reload of tool definitions against the simulator.
- **Important:** a reference MCP Apps host (or a hosted test page) for Alexa+, so a view can be checked without a device.
- **Important:** a way to send the `io.modelcontextprotocol/ui` client capability from the Python MCP SDK.
- **Nice-to-have:** a single reconciled MCP Apps spec page that fixes the field-name and message-shape contradictions.
- **Nice-to-have:** a clear error message and fix link for Bedrock `Operation not allowed` on new accounts.
