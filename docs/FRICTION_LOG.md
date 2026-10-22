# Friction log

Entries are written as they happened. Fields: task, steps, expected vs actual, severity, workaround, suggestion.

## 1. Alexa+ track has no starter repo or simulator link on the hackathon Resources page
- **Task:** find a starting point for an Alexa+ MCP add-on.
- **Steps:** read the Resources page; followed the Alexa+ section.
- **Expected:** a starter repo, like the Fire TV (8 samples) and Ring (`ring-api-helloworld`) tracks have.
- **Actual:** two links only, the MCP Apps docs and the generic MCP transport spec. Amazon's own Alexa+ MCP Toolkit
  quickstart and integration guide are not linked from the page; I found them by web search.
- **Severity:** medium (cost time on day one).
- **Workaround:** searched developer.amazon.com for "Alexa+ MCP toolkit quickstart".
- **Suggestion:** link the MCP Toolkit quickstart, the 500 ms latency and auth requirements, and a minimal
  "hello world" MCP server that passes the Alexa+ checks.

## 2. Auth requirements are demanding for a hackathon time box
- **Task:** plan authentication for the MCP server.
- **Expected:** a simple way to test without real account linking.
- **Actual:** the quickstart requires RFC 9728 protected-resource metadata, an OAuth 2.1 server with PKCE (S256),
  and a 401 without `WWW-Authenticate`. Dynamic Client Registration is not supported yet.
- **Severity:** medium.
- **Workaround:** the demo uses a default user id; the README documents where the token-derived id would plug in.
- **Suggestion:** provide a drop-in dev auth server or a "test mode" that skips account linking in the simulator.

## 3. Tool changes only take effect after `alexa-ai deploy`
- **Task:** understand the iteration loop.
- **Actual:** the quickstart says Alexa+ refreshes tool information only on deployment.
- **Severity:** low to medium. It slows the edit-test loop; hot reload against the simulator would help.

## 4. AWS credit codes exhausted before the deadline
- **Task:** get AWS credits for the AWS Builder mini challenge.
- **Actual:** the Resources and Rules pages say credit codes ran out on Oct 7. The rules still list a request deadline of
  Oct 21, which is contradictory.
- **Severity:** high for first-time AWS users: Bedrock needs an account and a payment method.
- **Suggestion:** state "sold out" at the top of the rules, and offer a no-card sandbox for Bedrock.

## 5. Bedrock playground: `ValidationException: Operation not allowed` on a brand-new account
- **Task:** call Amazon Nova Lite in the Bedrock playground (ap-southeast-2) to add a model layer.
- **Steps:** created an AWS account via Builder ID, opened Bedrock, chose Nova Lite, sent "hello".
- **Expected:** a model reply. The Model access page says serverless models are enabled automatically on first use.
- **Actual:** a red `ValidationException: Operation not allowed`, with no hint about the cause (account activation,
  plan restriction or payment verification).
- **Severity:** high. It blocked the AWS Builder mini challenge entirely.
- **Workaround:** none found. The submission does not use Bedrock.
- **Suggestion:** return an actionable message ("account not yet verified", "upgrade from the free plan") instead of a
  generic validation error.

## 6. `pip install mcp` pulls 2.x, which breaks 1.x code
- **Task:** install the MCP Python SDK and import `FastMCP`.
- **Actual:** the latest release (2.3.0) renamed `FastMCP` to `MCPServer` and changed other APIs. The import error
  itself is clear and suggests `mcp<2`, but existing tutorials and the quickstart pattern still assume 1.x.
- **Severity:** medium. **Workaround:** `pip install "mcp<2"`.
- **Suggestion:** state the supported SDK major version on the hackathon Resources page.

## 7. MCP Apps: the details are not where the hackathon page points
- **Task:** make the on-screen card an MCP App, as Alexa+ screens expect.
- **Steps:** followed the "Build with Agent Skills" link on the Resources page, then web-searched for the format.
- **Expected:** the metadata key, MIME type and message handshake.
- **Actual:** the linked API page is an overview that omits all three. They are in the spec file of the `ext-apps`
  repository (`specification/2026-01-26/apps.mdx`), which I found through search.
- **Severity:** medium. **Workaround:** read the spec file directly.
- **Suggestion:** link the spec file, and a minimal Python server example, from the Alexa+ resources.

## 8. MCP Apps spec contradicts itself in several places
- **Task:** implement the View's `ui/initialize` request and the host's replies.
- **Actual:** the spec names the field `appCapabilities` in the text but `capabilities` in its JSON example; lists
  `ui/resource-teardown` as a notification but shows it with an `id`; the CSP example uses `connect-src 'self'` while the
  stated default is `connect-src 'none'`; and the capability example uses protocol `2024-11-05` while the rest uses
  `2026-01-26`. The flat `ui/resourceUri` key is deprecated but SDKs still emit it.
- **Severity:** low to medium. **Workaround:** send both field names, tolerate both message shapes, and emit both the
  current and the legacy `_meta` key.
- **Suggestion:** reconcile the examples with the normative text.

## 9. Python MCP SDK cannot advertise the MCP Apps capability
- **Task:** have the simulator host advertise `io.modelcontextprotocol/ui` so the server can check it.
- **Actual:** `ClientSession` in `mcp` 1.x takes no capabilities argument, and `ClientCapabilities` has no `extensions`
  field, so a Python client cannot send it. The server therefore always declares the view and relies on the text fallback.
- **Severity:** low. **Workaround:** none; documented as a limitation.
- **Suggestion:** support client `extensions` in the Python SDK (the 2.x line appears to add an `extensions` parameter,
  but 2.x also renamed `FastMCP`, see entry 6).

## 10. Following the quickstart's tunnel advice with the Python SDK gives `421 Invalid Host header`
- **Task:** expose the server through a tunnel, as the Alexa+ quickstart suggests (it names `cloudflared`).
- **Actual:** the Python MCP SDK's DNS-rebinding protection accepts only `localhost` Host headers by default, so every
  request through a tunnel is refused with `421 Invalid Host header`. Nothing in the quickstart mentions it.
- **Severity:** medium (a developer following the docs gets a confusing error from the first remote request).
- **Workaround:** pass `TransportSecuritySettings(allowed_hosts=[...])` to `FastMCP`, naming the tunnel host. The server
  now reads the host from an environment variable and refuses wildcards, so the protection stays on.
- **Suggestion:** add that setting to the quickstart's local-development section.

## 11. Python 3.14: `pip install strands-agents mcp` stalled
- **Task:** install the MCP SDK and Strands Agents in a fresh venv on Python 3.14.
- **Steps:** `pip install mcp strands-agents uvicorn boto3` (first with `boto3` listed separately, then without).
- **Expected:** a normal install.
- **Actual:** first attempt failed with `ResolutionImpossible` because `boto3` was pinned separately (my mistake, since
  Strands brings its own). The next attempts appeared to hang for 15+ minutes with no output. Verbose logs showed two
  causes: pip backtracking through old `mcp` versions on `pyjwt[crypto]`, and repeated "Connection timed out while
  downloading" resumes from the package host (a flaky network, not an SDK bug).
- **Severity:** medium (lost about an hour of a one-day build).
- **Workaround:** `pip install --only-binary :all: cryptography pyjwt mcp uvicorn` so the resolver cannot backtrack
  onto source builds; verbose logging (`-v`) and a redirected log file to see what pip was doing.
- **Suggestion:** state tested Python versions for the MCP and Strands SDKs, and ship `pyjwt`/`cryptography` bounds
  that resolve cleanly on newer Pythons.
