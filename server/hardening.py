"""What changes once the server is reachable from the internet. Everything here is opt-in via environment variables,
so running locally behaves exactly as before.

    SAHAYAK_ALLOWED_HOSTS   comma-separated public hostnames the server may be reached by (e.g. the tunnel's name).
                            Without it the MCP SDK rejects any Host other than localhost (421 Invalid Host header),
                            which is its DNS-rebinding protection. We keep that protection on and add only these names.
    SAHAYAK_ACCESS_TOKEN    if set, every request must carry `Authorization: Bearer <token>`, else 401.
                            This is a shared secret for a demo, NOT the OAuth account linking Alexa+ requires.
"""
from __future__ import annotations

import hmac
import json
from urllib.parse import urlparse

from mcp.server.transport_security import TransportSecuritySettings

LOCAL_HOSTS = ["127.0.0.1:*", "localhost:*", "[::1]:*"]
LOCAL_ORIGINS = ["http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*"]
MIN_TOKEN_LENGTH = 16


def parse_hosts(value: str) -> list[str]:
    """'https://abc.trycloudflare.com/, other.example.com' -> ['abc.trycloudflare.com', 'other.example.com']."""
    hosts = []
    for raw in value.split(","):
        raw = raw.strip().lower()
        if not raw:
            continue
        host = (urlparse(raw).netloc if "://" in raw else raw).strip("/")
        if not host or "*" in host or "/" in host or " " in host:
            raise ValueError(f"Not a usable hostname in SAHAYAK_ALLOWED_HOSTS: {raw!r} (wildcards are refused on purpose)")
        hosts.append(host)
    return hosts


def security_settings(allowed_hosts_value: str) -> TransportSecuritySettings | None:
    """None keeps the SDK default (localhost only). Otherwise localhost plus exactly the named hosts."""
    hosts = parse_hosts(allowed_hosts_value)
    if not hosts:
        return None
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=LOCAL_HOSTS + hosts,
        allowed_origins=LOCAL_ORIGINS + [f"https://{h}" for h in hosts],
    )


def check_token(token: str) -> str:
    if len(token) < MIN_TOKEN_LENGTH:
        raise ValueError(f"SAHAYAK_ACCESS_TOKEN must be at least {MIN_TOKEN_LENGTH} characters; use a long random value")
    return token


class TokenGate:
    """ASGI middleware: reject requests without the right bearer token. Replies 401 with no WWW-Authenticate header,
    which is what the Alexa+ MCP Toolkit documents for unauthenticated requests."""

    def __init__(self, app, token: str):
        self.app = app
        self.token = check_token(token).encode()

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":          # lifespan and websocket messages pass straight through
            await self.app(scope, receive, send)
            return
        supplied = next((v for k, v in scope["headers"] if k == b"authorization"), b"")
        if supplied.startswith(b"Bearer ") and hmac.compare_digest(supplied[7:].strip(), self.token):
            await self.app(scope, receive, send)
            return
        body = json.dumps({"error": "unauthorized"}).encode()
        await send({"type": "http.response.start", "status": 401,
                    "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]})
        await send({"type": "http.response.body", "body": body})
