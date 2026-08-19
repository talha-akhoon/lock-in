"""Browser Web Push subscriptions. Cookie session only — not MCP."""

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_session_user, require_csrf
from app.models.domain import User
from app.services import push as push_service

router = APIRouter(tags=["push"])


class PushKeys(BaseModel):
    p256dh: str = Field(min_length=8, max_length=255)
    auth: str = Field(min_length=8, max_length=255)


class PushSubscribe(BaseModel):
    endpoint: str = Field(min_length=12, max_length=4096)
    keys: PushKeys

    @field_validator("endpoint")
    @classmethod
    def https_or_local(cls, value: str) -> str:
        if value.startswith("https://"):
            return value
        if value.startswith(("http://127.0.0.1", "http://localhost")):
            return value
        raise ValueError("Push endpoint must be HTTPS")


class PushUnsubscribe(BaseModel):
    endpoint: str = Field(min_length=12, max_length=4096)


@router.get("/me/push/config")
def push_config(_user: User = Depends(get_session_user)) -> dict:
    return push_service.config_payload()


@router.post(
    "/me/push/subscriptions",
    dependencies=[Depends(require_csrf)],
    status_code=status.HTTP_201_CREATED,
)
def subscribe(
    payload: PushSubscribe,
    request: Request,
    user: User = Depends(get_session_user),
    db: Session = Depends(get_db),
) -> dict:
    agent = request.headers.get("user-agent")
    row = push_service.upsert(
        db,
        user_id=user.id,
        endpoint=payload.endpoint,
        p256dh=payload.keys.p256dh,
        auth=payload.keys.auth,
        user_agent=agent[:512] if agent else None,
    )
    db.commit()
    return push_service.public_row(row)


@router.post(
    "/me/push/subscriptions/unsubscribe",
    dependencies=[Depends(require_csrf)],
)
def unsubscribe(
    payload: PushUnsubscribe,
    user: User = Depends(get_session_user),
    db: Session = Depends(get_db),
) -> dict:
    removed = push_service.remove(db, user_id=user.id, endpoint=payload.endpoint)
    db.commit()
    return {"removed": removed}
