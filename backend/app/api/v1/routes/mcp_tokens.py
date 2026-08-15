"""Create, list and revoke personal access tokens. Cookie session only."""

import uuid

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_session_user, require_csrf
from app.models.domain import User
from app.services import mcp_tokens as token_service

router = APIRouter(tags=["mcp"])


class McpTokenCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)


@router.get("/me/mcp-tokens")
def list_mcp_tokens(
    user: User = Depends(get_session_user), db: Session = Depends(get_db)
) -> list[dict]:
    return [
        token_service.public_row(row) for row in token_service.list_active(db, user.id)
    ]


@router.post(
    "/me/mcp-tokens",
    dependencies=[Depends(require_csrf)],
    status_code=status.HTTP_201_CREATED,
)
def create_mcp_token(
    payload: McpTokenCreate,
    user: User = Depends(get_session_user),
    db: Session = Depends(get_db),
) -> dict:
    row, raw = token_service.mint(db, user_id=user.id, name=payload.name)
    db.commit()
    return token_service.public_row(row, token=raw)


@router.delete(
    "/me/mcp-tokens/{token_id}",
    dependencies=[Depends(require_csrf)],
    status_code=status.HTTP_204_NO_CONTENT,
)
def revoke_mcp_token(
    token_id: uuid.UUID,
    user: User = Depends(get_session_user),
    db: Session = Depends(get_db),
) -> Response:
    token_service.revoke(db, token_id=token_id, user_id=user.id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
