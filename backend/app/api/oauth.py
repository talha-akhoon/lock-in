"""OAuth 2.1 + PKCE for ChatGPT MCP connectors. Lives at the origin root."""

from html import escape
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import SESSION_COOKIE, get_session_user
from app.models.domain import User
from app.services import oauth as oauth_service

router = APIRouter(tags=["oauth"])


def _cors(payload, status_code: int = 200) -> JSONResponse:
    response = JSONResponse(payload, status_code=status_code)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response


@router.options("/.well-known/oauth-protected-resource")
@router.options("/.well-known/oauth-protected-resource/mcp")
@router.options("/.well-known/oauth-authorization-server")
@router.options("/oauth/token")
@router.options("/oauth/register")
def oauth_preflight() -> JSONResponse:
    return _cors({})


@router.get("/.well-known/oauth-protected-resource")
@router.get("/.well-known/oauth-protected-resource/mcp")
def protected_resource(request: Request) -> JSONResponse:
    return _cors(
        oauth_service.protected_resource_metadata(oauth_service.public_origin(request))
    )


@router.get("/.well-known/oauth-authorization-server")
def authorization_server(request: Request) -> JSONResponse:
    return _cors(
        oauth_service.authorization_metadata(oauth_service.public_origin(request))
    )


@router.get("/oauth/authorize", response_model=None)
def authorize(
    request: Request,
    response_type: str,
    client_id: str,
    redirect_uri: str,
    code_challenge: str,
    code_challenge_method: str = "S256",
    state: str | None = None,
    resource: str | None = None,
    scope: str | None = None,
    db: Session = Depends(get_db),
) -> HTMLResponse | RedirectResponse:
    origin = oauth_service.public_origin(request)
    expected = oauth_service.resource_url(origin)
    if response_type != "code":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "response_type must be code")
    if code_challenge_method != "S256":
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "code_challenge_method must be S256"
        )
    if resource and resource.rstrip("/") != expected.rstrip("/"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown resource")
    if not oauth_service.redirect_allowed(
        db, client_id=client_id, redirect_uri=redirect_uri
    ):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "redirect_uri is not allowed")

    try:
        user = get_session_user(token=request.cookies.get(SESSION_COOKIE), db=db)
    except HTTPException:
        nxt = quote(
            str(request.url.path)
            + (f"?{request.url.query}" if request.url.query else "")
        )
        return RedirectResponse(f"/login?next={nxt}", status_code=302)

    pending = oauth_service.sign_pending(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "code_challenge": code_challenge,
            "state": state,
            "resource": resource or expected,
            "user_id": str(user.id),
        }
    )
    return HTMLResponse(_consent_page(user, pending))


@router.post("/oauth/authorize")
def decide(
    request: Request,
    pending: str = Form(),
    decision: str = Form(),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    claims = oauth_service.read_pending(pending)
    user = get_session_user(token=request.cookies.get(SESSION_COOKIE), db=db)
    if str(user.id) != claims["user_id"]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Session does not match")

    params: dict[str, str] = {}
    if claims.get("state"):
        params["state"] = claims["state"]
    if decision != "approve":
        params["error"] = "access_denied"
        return RedirectResponse(
            oauth_service.redirect_with(claims["redirect_uri"], **params),
            status_code=302,
        )

    code = oauth_service.issue_code(
        db,
        user_id=user.id,
        client_id=claims["client_id"],
        redirect_uri=claims["redirect_uri"],
        code_challenge=claims["code_challenge"],
        resource=claims["resource"],
    )
    db.commit()
    params["code"] = code
    return RedirectResponse(
        oauth_service.redirect_with(claims["redirect_uri"], **params),
        status_code=302,
    )


@router.post("/oauth/token")
def token(
    request: Request,
    grant_type: str = Form(),
    code: str = Form(),
    redirect_uri: str = Form(),
    client_id: str = Form(),
    code_verifier: str = Form(),
    resource: str | None = Form(default=None),
    db: Session = Depends(get_db),
) -> JSONResponse:
    if grant_type != "authorization_code":
        return _cors({"error": "unsupported_grant_type"}, 400)
    origin = oauth_service.public_origin(request)
    expected = oauth_service.resource_url(origin)
    try:
        raw, _user = oauth_service.exchange_code(
            db,
            code=code,
            client_id=client_id,
            redirect_uri=redirect_uri,
            code_verifier=code_verifier,
            resource=resource or expected,
        )
    except HTTPException as exc:
        return _cors(
            {"error": "invalid_grant", "error_description": str(exc.detail)}, 400
        )
    db.commit()
    response = _cors(
        {
            "access_token": raw,
            "token_type": "Bearer",
            "expires_in": oauth_service.TOKEN_LIFETIME_SECONDS,
            "scope": oauth_service.SCOPE,
        }
    )
    response.headers["Cache-Control"] = "no-store"
    return response


class ClientRegistration(BaseModel):
    redirect_uris: list[str] = Field(min_length=1)
    client_name: str | None = None
    token_endpoint_auth_method: str = "none"
    grant_types: list[str] | None = None
    response_types: list[str] | None = None


@router.post("/oauth/register")
def register(
    payload: ClientRegistration, db: Session = Depends(get_db)
) -> JSONResponse:
    client = oauth_service.register_client(
        db,
        redirect_uris=payload.redirect_uris,
        client_name=payload.client_name,
        token_endpoint_auth_method=payload.token_endpoint_auth_method,
    )
    db.commit()
    return _cors(
        {
            "client_id": client.client_id,
            "client_name": client.client_name,
            "redirect_uris": client.redirect_uris,
            "token_endpoint_auth_method": client.token_endpoint_auth_method,
            "grant_types": ["authorization_code"],
            "response_types": ["code"],
        },
        201,
    )


def _consent_page(user: User, pending: str) -> str:
    name = escape(user.display_name)
    token = escape(pending, quote=True)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Connect LockIn</title>
  <style>
    body {{ margin: 0; min-height: 100vh; display: grid; place-items: center;
      background: #121412; color: #e8eee4; font: 16px/1.5 ui-sans-serif, system-ui; }}
    main {{ width: min(440px, calc(100% - 32px)); padding: 32px; border: 1px solid #2a3028;
      border-radius: 16px; background: #181c18; }}
    h1 {{ margin: 0 0 8px; font-size: 24px; }}
    p {{ color: #9aa394; }}
    b {{ color: #e8eee4; }}
    form {{ display: flex; gap: 12px; margin-top: 24px; }}
    button {{ flex: 1; padding: 12px 16px; border-radius: 10px; border: 0; font-weight: 650; cursor: pointer; }}
    .approve {{ background: #b6e388; color: #121412; }}
    .deny {{ background: #2a1715; color: #ff8d86; }}
  </style>
</head>
<body>
  <main>
    <h1>Connect your LLM</h1>
    <p>Signed in as <b>{name}</b>. This app will be able to read your goals, see teammates'
    team-visible progress, and log today's check-in. Private goals stay in LockIn.
    Connecting shares that view with the LLM provider.</p>
    <form method="post" action="/oauth/authorize">
      <input type="hidden" name="pending" value="{token}" />
      <button class="deny" name="decision" value="deny" type="submit">Deny</button>
      <button class="approve" name="decision" value="approve" type="submit">Allow</button>
    </form>
  </main>
</body>
</html>"""
