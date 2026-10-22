import pytest
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from server.hardening import LOCAL_HOSTS, TokenGate, check_token, parse_hosts, security_settings

TOKEN = "a-long-random-demo-token-123"


def test_hosts_are_cleaned_up_from_urls_and_lists():
    assert parse_hosts("https://Abc.trycloudflare.com/, other.example.com") == ["abc.trycloudflare.com", "other.example.com"]
    assert parse_hosts("") == [] and parse_hosts(" , ") == []


@pytest.mark.parametrize("bad", ["*", "*.example.com", "evil.com/path", "a b", "https://"])
def test_wildcards_and_junk_hosts_are_refused_so_protection_cannot_be_switched_off_by_accident(bad):
    with pytest.raises(ValueError):
        parse_hosts(bad)


def test_default_is_the_sdk_default_localhost_only():
    assert security_settings("") is None


def test_named_hosts_are_added_to_localhost_and_protection_stays_on():
    s = security_settings("demo.trycloudflare.com")
    assert s.enable_dns_rebinding_protection is True
    assert "demo.trycloudflare.com" in s.allowed_hosts and set(LOCAL_HOSTS) <= set(s.allowed_hosts)
    assert "https://demo.trycloudflare.com" in s.allowed_origins
    assert "other.example.com" not in s.allowed_hosts


def test_short_tokens_are_refused():
    with pytest.raises(ValueError):
        check_token("secret")
    assert check_token(TOKEN) == TOKEN


def _client():
    inner = Starlette(routes=[Route("/mcp", lambda r: PlainTextResponse("ok"), methods=["GET", "POST"])])
    inner.add_middleware(TokenGate, token=TOKEN)
    return TestClient(inner)


def test_requests_without_the_token_get_401_and_no_www_authenticate_header():
    r = _client().post("/mcp")
    assert r.status_code == 401
    assert "www-authenticate" not in {k.lower() for k in r.headers}  # what the Alexa+ MCP Toolkit documents


@pytest.mark.parametrize("header", ["Bearer wrong-token-wrong-token", "Bearer ", "Basic " + TOKEN, TOKEN, "bearer " + TOKEN])
def test_wrong_or_malformed_credentials_are_rejected(header):
    assert _client().post("/mcp", headers={"Authorization": header}).status_code == 401


def test_token_in_the_query_string_does_not_count():
    assert _client().post("/mcp?token=" + TOKEN).status_code == 401


def test_the_right_token_gets_through():
    r = _client().post("/mcp", headers={"Authorization": f"Bearer {TOKEN}"})
    assert r.status_code == 200 and r.text == "ok"
