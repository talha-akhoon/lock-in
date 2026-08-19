"""Internal jobs. Not cookie-session; HMAC locally, Google OIDC in production."""

import hashlib
import hmac
import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.session import get_db
from app.services import notification_dispatch

router = APIRouter(tags=["internal"])

DISPATCH_SERVICE_ACCOUNT = "lockin-github@lockin-505614.iam.gserviceaccount.com"
DISPATCH_HMAC_MESSAGE = b"lockin-notification-dispatch"


def dispatch_hmac_token() -> str:
    return hmac.new(
        get_settings().secret_key.encode(),
        DISPATCH_HMAC_MESSAGE,
        hashlib.sha256,
    ).hexdigest()


def _audience() -> str:
    origin = get_settings().public_origin.strip().rstrip("/")
    return origin or "https://lockin.talhaakhoon.dev"


def _hmac_ok(provided: str | None) -> bool:
    expected = dispatch_hmac_token()
    if not provided or len(provided) != len(expected):
        return False
    return secrets.compare_digest(provided, expected)


def _oidc_ok(bearer: str | None) -> bool:
    if not bearer or not bearer.lower().startswith("bearer "):
        return False
    token = bearer.split(" ", 1)[1].strip()
    if not token:
        return False
    try:
        claims = google_id_token.verify_oauth2_token(
            token, google_requests.Request(), _audience()
        )
    except ValueError:
        return False
    return claims.get("email") == DISPATCH_SERVICE_ACCOUNT


def require_dispatcher(
    x_lockin_dispatch: str | None = Header(default=None, alias="X-LockIn-Dispatch"),
    authorization: str | None = Header(default=None),
) -> None:
    if _hmac_ok(x_lockin_dispatch) or _oidc_ok(authorization):
        return
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid dispatch token")


@router.post(
    "/internal/notifications/dispatch",
    dependencies=[Depends(require_dispatcher)],
)
def dispatch_notifications(db: Session = Depends(get_db)) -> dict:
    notification_dispatch.run(db)
    db.commit()
    return {"status": "ok"}
