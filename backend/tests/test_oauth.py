"""OAuth 2.1 + PKCE for ChatGPT MCP connectors."""

import re
import secrets
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

from app.models.domain import McpToken
from app.services.oauth import s256_challenge

CHATGPT_REDIRECT = "https://chatgpt.com/connector/oauth/lockin-test"
CHATGPT_CLIENT = "https://chatgpt.com/.well-known/oauth-client"


def _pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(32)
    return verifier, s256_challenge(verifier)


def _authorize_query(**extra: str) -> dict[str, str]:
    _verifier, challenge = _pkce()
    return {
        "response_type": "code",
        "client_id": CHATGPT_CLIENT,
        "redirect_uri": CHATGPT_REDIRECT,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "resource": "http://testserver/mcp",
        "state": "abc",
        **extra,
    }


def _pending(html: str) -> str:
    match = re.search(r'name="pending" value="([^"]+)"', html)
    assert match, html
    return match.group(1)


def test_oauth_metadata_is_public_and_cors_open(anon) -> None:
    resource = anon.get("/.well-known/oauth-protected-resource")
    server = anon.get("/.well-known/oauth-authorization-server")
    path_aware = anon.get("/.well-known/oauth-protected-resource/mcp")

    assert resource.status_code == 200
    assert resource.json()["resource"] == "http://testserver/mcp"
    assert resource.json()["authorization_servers"] == ["http://testserver"]
    assert (
        server.json()["authorization_endpoint"] == "http://testserver/oauth/authorize"
    )
    assert server.json()["client_id_metadata_document_supported"] is True
    assert "openid" not in server.json()["scopes_supported"]
    assert path_aware.json()["resource"] == resource.json()["resource"]
    assert resource.headers["access-control-allow-origin"] == "*"
    assert anon.options("/oauth/token").headers["access-control-allow-origin"] == "*"


def test_authorize_sends_an_anonymous_user_to_login(anon) -> None:
    response = anon.get(
        "/oauth/authorize",
        params=_authorize_query(),
        follow_redirects=False,
    )

    assert response.status_code == 302
    location = urlparse(response.headers["location"])
    assert location.path == "/login"
    nxt = parse_qs(location.query)["next"][0]
    assert nxt.startswith("/oauth/authorize")
    assert "code_challenge=" in nxt


def test_unknown_redirect_is_rejected(team_setup) -> None:
    response = team_setup.admin_client.get(
        "/oauth/authorize",
        params=_authorize_query(redirect_uri="https://evil.example/cb"),
    )
    assert response.status_code == 400


def test_chatgpt_oauth_mints_a_revocable_mcp_token(team_setup, app, db) -> None:
    verifier, challenge = _pkce()
    client = team_setup.admin_client
    consent = client.get(
        "/oauth/authorize",
        params=_authorize_query(code_challenge=challenge),
    )
    assert consent.status_code == 200
    assert "Connect your LLM" in consent.text
    assert team_setup.admin.display_name in consent.text

    approved = client.post(
        "/oauth/authorize",
        data={"pending": _pending(consent.text), "decision": "approve"},
        follow_redirects=False,
    )
    assert approved.status_code == 302
    redirected = urlparse(approved.headers["location"])
    assert redirected.scheme == "https"
    assert redirected.netloc == "chatgpt.com"
    params = parse_qs(redirected.query)
    assert params["state"] == ["abc"]
    code = params["code"][0]

    token = client.post(
        "/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": CHATGPT_REDIRECT,
            "client_id": CHATGPT_CLIENT,
            "code_verifier": verifier,
            "resource": "http://testserver/mcp",
        },
    )
    assert token.status_code == 200, token.text
    assert token.headers["cache-control"] == "no-store"
    raw = token.json()["access_token"]
    assert raw.startswith("lin_")

    listed = client.get("/api/v1/me/mcp-tokens").json()
    assert listed[0]["name"] == "ChatGPT"
    stored = db.get(McpToken, listed[0]["id"])
    assert stored is not None
    assert raw not in stored.token_hash

    with TestClient(app) as mcp:
        assert (
            mcp.post("/mcp", headers={"Authorization": f"Bearer {raw}"}).status_code
            != 401
        )


def test_wrong_pkce_verifier_is_rejected(team_setup) -> None:
    _verifier, challenge = _pkce()
    client = team_setup.admin_client
    consent = client.get(
        "/oauth/authorize",
        params=_authorize_query(code_challenge=challenge),
    )
    approved = client.post(
        "/oauth/authorize",
        data={"pending": _pending(consent.text), "decision": "approve"},
        follow_redirects=False,
    )
    code = parse_qs(urlparse(approved.headers["location"]).query)["code"][0]

    denied = client.post(
        "/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": CHATGPT_REDIRECT,
            "client_id": CHATGPT_CLIENT,
            "code_verifier": "not-the-verifier",
            "resource": "http://testserver/mcp",
        },
    )
    assert denied.status_code == 400
    assert denied.json()["error"] == "invalid_grant"


def test_deny_returns_access_denied(team_setup) -> None:
    consent = team_setup.admin_client.get("/oauth/authorize", params=_authorize_query())
    denied = team_setup.admin_client.post(
        "/oauth/authorize",
        data={"pending": _pending(consent.text), "decision": "deny"},
        follow_redirects=False,
    )
    assert denied.status_code == 302
    params = parse_qs(urlparse(denied.headers["location"]).query)
    assert params["error"] == ["access_denied"]
    assert params["state"] == ["abc"]


def test_dynamic_client_registration(anon, team_setup) -> None:
    created = anon.post(
        "/oauth/register",
        json={
            "client_name": "Lab client",
            "redirect_uris": ["https://lab.example/cb"],
            "token_endpoint_auth_method": "none",
        },
    )
    assert created.status_code == 201
    client_id = created.json()["client_id"]

    consent = team_setup.admin_client.get(
        "/oauth/authorize",
        params=_authorize_query(
            client_id=client_id, redirect_uri="https://lab.example/cb"
        ),
    )
    assert consent.status_code == 200
