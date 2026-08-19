"""Aggregates the per-resource route modules into the v1 API."""

from fastapi import APIRouter

from app.api.v1.routes import (
    admin,
    auth,
    challenges,
    checkins,
    goals,
    invitations,
    mcp_tokens,
    notifications,
    push,
    teams,
)

router = APIRouter()


@router.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}


for module in (
    auth,
    teams,
    invitations,
    challenges,
    goals,
    checkins,
    notifications,
    admin,
    mcp_tokens,
    push,
):
    router.include_router(module.router)
