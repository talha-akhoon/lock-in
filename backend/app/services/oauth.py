"""OAuth 2.1 authorization server for ChatGPT and other MCP connectors."""

import base64
import hashlib
import ipaddress
import secrets
import socket
import uuid
from datetime import timedelta
from urllib.parse import urlencode, urlparse

import bcrypt
import jwt
import requests
from fastapi import HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.domain import OAuthAuthCode, OAuthClient, User
from app.services import mcp_tokens
from app.services.clock import utcnow

SCOPE = "lockin"
CODE_TTL = timedelta(minutes=10)
PENDING_TTL = timedelta(minutes=10)
TOKEN_LIFETIME_SECONDS = 60 * 60 * 24 * 365
CHATGPT_REDIRECTS = (
    "https://chatgpt.com/connector/oauth/",
    "https://chatgpt.com/connector_platform_oauth_redirect",
)


def origin_from_headers(headers: dict[str, str]) -> str:
    configured = get_settings().public_origin.strip().rstrip("/")
    if configured:
        return configured
    proto = (headers.get("x-forwarded-proto") or "http").split(",")[0].strip()
    host = (
        (headers.get("x-forwarded-host") or headers.get("host") or "localhost")
        .split(",")[0]
        .strip()
    )
    return f"{proto}://{host}"


def public_origin(request: Request) -> str:
    return origin_from_headers({k.lower(): v for k, v in request.headers.items()})


def resource_url(origin: str) -> str:
    return f"{origin}/mcp"


def s256_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def _is_chatgpt_redirect(uri: str) -> bool:
    return uri == CHATGPT_REDIRECTS[1] or uri.startswith(CHATGPT_REDIRECTS[0])


def _is_private_host(hostname: str) -> bool:
    if hostname in {"localhost", "127.0.0.1", "::1"}:
        return True
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        try:
            address = ipaddress.ip_address(socket.getaddrinfo(hostname, None)[0][4][0])
        except (OSError, ValueError, IndexError):
            return True
    return address.is_private or address.is_loopback or address.is_link_local


def _fetch_cimd(client_id: str) -> dict | None:
    parsed = urlparse(client_id)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or _is_private_host(parsed.hostname)
    ):
        return None
    try:
        response = requests.get(
            client_id,
            timeout=5,
            allow_redirects=False,
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def redirect_allowed(db: Session, *, client_id: str, redirect_uri: str) -> bool:
    if _is_chatgpt_redirect(redirect_uri):
        return True
    stored = db.get(OAuthClient, client_id)
    if stored and redirect_uri in (stored.redirect_uris or []):
        return True
    if client_id.startswith("https://"):
        meta = _fetch_cimd(client_id)
        uris = meta.get("redirect_uris") if meta else None
        if isinstance(uris, list) and redirect_uri in uris:
            return True
    return False


def register_client(
    db: Session,
    *,
    redirect_uris: list[str],
    client_name: str | None = None,
    token_endpoint_auth_method: str = "none",
) -> OAuthClient:
    if not redirect_uris:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "redirect_uris is required")
    for uri in redirect_uris:
        parsed = urlparse(uri)
        if parsed.scheme not in {"https", "http"} or not parsed.netloc:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "redirect_uris must be absolute URLs"
            )
    client = OAuthClient(
        client_id=str(uuid.uuid4()),
        client_name=client_name,
        redirect_uris=redirect_uris,
        token_endpoint_auth_method=token_endpoint_auth_method or "none",
    )
    db.add(client)
    db.flush()
    return client


def sign_pending(payload: dict) -> str:
    now = utcnow()
    return jwt.encode(
        {**payload, "iat": now, "exp": now + PENDING_TTL},
        get_settings().secret_key,
        algorithm="HS256",
    )


def read_pending(token: str) -> dict:
    try:
        return jwt.decode(token, get_settings().secret_key, algorithms=["HS256"])
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "This authorization request has expired"
        ) from exc


def issue_code(
    db: Session,
    *,
    user_id: uuid.UUID,
    client_id: str,
    redirect_uri: str,
    code_challenge: str,
    resource: str,
) -> str:
    raw = secrets.token_urlsafe(32)
    db.add(
        OAuthAuthCode(
            code_hash=bcrypt.hashpw(raw.encode(), bcrypt.gensalt()).decode(),
            client_id=client_id,
            user_id=user_id,
            redirect_uri=redirect_uri,
            code_challenge=code_challenge,
            resource=resource,
            expires_at=utcnow() + CODE_TTL,
        )
    )
    db.flush()
    return raw


def exchange_code(
    db: Session,
    *,
    code: str,
    client_id: str,
    redirect_uri: str,
    code_verifier: str,
    resource: str,
) -> tuple[str, User]:
    now = utcnow()
    rows = list(
        db.scalars(select(OAuthAuthCode).where(OAuthAuthCode.consumed_at.is_(None)))
    )
    match = next(
        (row for row in rows if bcrypt.checkpw(code.encode(), row.code_hash.encode())),
        None,
    )
    if (
        match is None
        or match.client_id != client_id
        or match.redirect_uri != redirect_uri
        or match.expires_at <= now
    ):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid authorization code")
    if s256_challenge(code_verifier) != match.code_challenge:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "PKCE verification failed")
    if match.resource.rstrip("/") != resource.rstrip("/"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "resource does not match")
    match.consumed_at = now
    name = _token_name(client_id)
    _row, raw = mcp_tokens.mint(db, user_id=match.user_id, name=name)
    return raw, match.user


def _token_name(client_id: str) -> str:
    host = urlparse(client_id).hostname or ""
    if "chatgpt.com" in host or "openai.com" in host:
        return "ChatGPT"
    if host:
        return host[:80]
    return "OAuth client"


def authorization_metadata(origin: str) -> dict:
    return {
        "issuer": origin,
        "authorization_endpoint": f"{origin}/oauth/authorize",
        "token_endpoint": f"{origin}/oauth/token",
        "registration_endpoint": f"{origin}/oauth/register",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["none"],
        "client_id_metadata_document_supported": True,
        "scopes_supported": [SCOPE],
    }


def protected_resource_metadata(origin: str) -> dict:
    return {
        "resource": resource_url(origin),
        "authorization_servers": [origin],
        "scopes_supported": [SCOPE],
        "bearer_methods_supported": ["header"],
        "resource_name": "LockIn",
    }


def www_authenticate(origin: str) -> str:
    metadata = f"{origin}/.well-known/oauth-protected-resource"
    return (
        'Bearer error="invalid_token", '
        'error_description="Authentication required", '
        f'resource_metadata="{metadata}"'
    )


def redirect_with(redirect_uri: str, **params: str) -> str:
    separator = "&" if urlparse(redirect_uri).query else "?"
    return f"{redirect_uri}{separator}{urlencode(params)}"
