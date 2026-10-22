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

## 8. MCP Apps spec contradicts itself in several places (checked against the spec file and the SDK types)
- **Task:** implement the View's `ui/initialize` request and the host's replies.
- **Actual** (line numbers are from `specification/2026-01-26/apps.mdx` in the ext-apps repository):
  1. The spec's transport snippet (lines 461-465) sends method `initialize` with `capabilities` and `clientInfo`, but the
     text and examples (lines 512, 756-759) and the SDK's `McpUiInitializeRequest` type specify method `ui/initialize`
     with `appInfo`, `appCapabilities` and `protocolVersion`. My first version followed the snippet's names and omitted
     the required `appInfo`; it only came to light when I checked the messages against the SDK types.
  2. `ui/resource-teardown` is described as "Host notifies View" (line 1171) but is shown as a request with an `id` and a
     response; the text lists `params: { reason }` while the SDK type is `params: {}`.
  3. The default CSP is `connect-src 'none'` (line 283), but the spec's own "CSP Construction" code (line 1737) produces
     `connect-src 'self'` when no CSP is declared, which is looser than the stated default.
- **Severity:** medium for 1 (it produces a View a strict host may reject), low for 2, and medium for 3 (security default).
- **Workaround:** treat the SDK's `src/spec.types.ts` as authoritative, and keep a test that fixes the field names.
- **Suggestion:** make the transport snippet match the types, call teardown a request, and make the CSP example use
  `connect-src` with `'none'` as its fallback, as it already does for `frame-src`.

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

## 11. A tool annotated `-> dict` silently sends no `structuredContent`, and MCP Apps views read it
- **Task:** make the on-screen card (an MCP App view) draw from a tool's result.
- **Steps:** returned a plain `dict` from each tool, annotated `-> dict`, and built the view to read
  `result.structuredContent`, as the MCP Apps spec describes the tool result.
- **Expected:** the dict arrives as `structuredContent`.
- **Actual:** with `mcp` 1.30 a bare `dict` annotation produces no output schema and no `structuredContent`; the result
  carries only a JSON text blob. Nothing warns about it. My own simulator hid the problem by parsing that text, so it
  only surfaced while building a standalone test page that passes the server's result through untouched. A real host
  would have given the view an empty result.
- **Severity:** medium to high: the failure is silent and only appears on a host that does not parse text.
- **Workaround:** annotate tools `-> dict[str, Any]` (the SDK then emits `structuredContent`), make the view fall back
  to parsing the JSON text, and test `structuredContent` against a live server.
- **Suggestion:** warn when a tool returns a dict but no output schema is declared, and say in the MCP Apps docs that
  views need `structuredContent`.

## 12. Python 3.14: `pip install strands-agents mcp` stalled
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
