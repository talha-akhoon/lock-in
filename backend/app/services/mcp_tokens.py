"""Mint, look up and revoke personal access tokens for the MCP endpoint."""

import secrets
import uuid

import bcrypt
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.domain import McpToken, User
from app.services.clock import utcnow

TOKEN_PREFIX = "lin_"
# `lin_` plus enough of the secret to narrow the bcrypt comparison.
STORED_PREFIX_LEN = 12


def mint(db: Session, *, user_id: uuid.UUID, name: str) -> tuple[McpToken, str]:
    """Return the row and the plaintext token. The secret is shown only here."""
    raw = f"{TOKEN_PREFIX}{secrets.token_urlsafe(32)}"
    row = McpToken(
        user_id=user_id,
        name=name.strip(),
        token_hash=bcrypt.hashpw(raw.encode(), bcrypt.gensalt()).decode(),
        prefix=raw[:STORED_PREFIX_LEN],
    )
    db.add(row)
    db.flush()
    return row, raw


def list_active(db: Session, user_id: uuid.UUID) -> list[McpToken]:
    return list(
        db.scalars(
            select(McpToken)
            .where(McpToken.user_id == user_id, McpToken.revoked_at.is_(None))
            .order_by(McpToken.created_at.desc())
        ).all()
    )


def revoke(db: Session, *, token_id: uuid.UUID, user_id: uuid.UUID) -> None:
    row = db.get(McpToken, token_id)
    if not row or row.user_id != user_id or row.revoked_at:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Token not found")
    row.revoked_at = utcnow()


def authenticate(db: Session, raw: str) -> User | None:
    if not raw.startswith(TOKEN_PREFIX) or len(raw) < STORED_PREFIX_LEN:
        return None
    candidates = db.scalars(
        select(McpToken)
        .options(selectinload(McpToken.user))
        .where(
            McpToken.prefix == raw[:STORED_PREFIX_LEN],
            McpToken.revoked_at.is_(None),
        )
    ).all()
    for item in candidates:
        if bcrypt.checkpw(raw.encode(), item.token_hash.encode()):
            item.last_used_at = utcnow()
            return item.user
    return None


def public_row(row: McpToken, *, token: str | None = None) -> dict:
    payload = {
        "id": row.id,
        "name": row.name,
        "prefix": row.prefix,
        "last_used_at": row.last_used_at,
        "created_at": row.created_at,
    }
    if token is not None:
        payload["token"] = token
    return payload
