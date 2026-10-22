# Putting the MCP server on a public URL

Alexa+ connects to an MCP server at a **remote URL**, so a server on `127.0.0.1` is not reachable by it. This guide
makes the server reachable from the internet for a demo, and says what that does and does not give you.

## Read this first

- **A public URL is not required by the hackathon rules.** The repo and a demo video are what is judged.
- **This does not make Sahayak connectable to real Alexa+.** Alexa+ requires OAuth 2.1 account linking (PKCE),
  protected-resource metadata and an authorization server; Sahayak has none of that. What you get here is a reachable,
  protected endpoint you can show working from outside your machine.
- **Anything you expose is reachable by anyone who has the URL.** The server has a single shared `demo` user, so
  always run it with an access token (below) and shut it down when you are done.
- The tunnel services below are third parties that relay your traffic. Do not put real personal data through them.

## The three settings

The server is unchanged locally. These environment variables switch on what a public URL needs:

| Variable | What it does |
|---|---|
| `SAHAYAK_ALLOWED_HOSTS` | The public hostname(s) the server may be reached by, e.g. `https://abc.example.com`. Without it, the MCP SDK answers `421 Invalid Host header` to every request that is not for `localhost` (its DNS-rebinding protection). Only the names you list are added; wildcards are refused. |
| `SAHAYAK_ACCESS_TOKEN` | A shared secret (16+ characters). Every request must send `Authorization: Bearer <token>`, otherwise the server replies `401` with no `WWW-Authenticate` header, as Amazon's quickstart describes. This is a demo gate, **not** OAuth. |
| `SAHAYAK_MCP_TOKEN` | For clients (the simulator, `eval.smoke`): the token to send. |

## Option A: a tunnel with nothing to install (Windows 11 already has `ssh`)

1. Make a token: `python -c "import secrets; print(secrets.token_urlsafe(24))"`
2. Open a tunnel to the server's port **before** starting the server, because the public name is only known afterwards:

   ```powershell
   ssh -R 80:127.0.0.1:8000 nokey@localhost.run
   ```

   It prints a line like `https://abcd1234.lhr.life`. That host is your public name. Leave this window open.
3. In a second terminal, start the server with that name and your token:

   ```powershell
   $env:SAHAYAK_ALLOWED_HOSTS = "https://abcd1234.lhr.life"
   $env:SAHAYAK_ACCESS_TOKEN  = "<your token>"
   python -m server.mcp_server
   ```
4. Check it from outside (a phone on mobile data works well, or any other machine):

   ```powershell
   $h = @{ Authorization = "Bearer <your token>"; Accept = "application/json, text/event-stream" }
   Invoke-WebRequest https://abcd1234.lhr.life/mcp -Method POST -Headers $h -ContentType "application/json" `
     -Body '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"t","version":"0"}}}'
   ```

   You should get `200` with a `protocolVersion` of `2025-11-25`. Without the header you should get `401`.
5. To run the **whole demo against the public URL** (the simulator talking to your server over the internet):

   ```powershell
   $env:SAHAYAK_MCP_URL   = "https://abcd1234.lhr.life/mcp"
   $env:SAHAYAK_MCP_TOKEN = "<your token>"
   python -m web.app
   ```

Free tunnel URLs change every time and can drop. Start a new tunnel, then restart the server with the new name.

## Option B: Cloudflare quick tunnel

Amazon's quickstart suggests `cloudflared` for local development. It needs a download (about 30 MB):

```powershell
cloudflared tunnel --url http://127.0.0.1:8000
```

It prints an `https://<words>.trycloudflare.com` URL; use that host for `SAHAYAK_ALLOWED_HOSTS` and carry on from step 3.

## Option C: host it on AWS (not done)

A container on AWS App Runner or ECS would give a stable URL, and would count as an AWS integration for the AWS Builder
challenge. It needs a working AWS account (a Bedrock "Operation not allowed" error blocked this one), a Dockerfile, and a
decision about the database, because SQLite on a container disk is lost when the container restarts. It was not attempted.

## Local checks on Windows

Use `127.0.0.1`, not `localhost`, in URLs on Windows. `localhost` may try IPv6 first and wait for it to fail, which added
about 280 ms to every new connection in testing, enough to make a healthy server look slower than Alexa+'s 500 ms budget.

```powershell
python -m eval.smoke http://127.0.0.1:8000/mcp
```
