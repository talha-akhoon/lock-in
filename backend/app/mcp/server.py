"""Streamable HTTP MCP server mounted at /mcp."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date
from typing import Any

from fastapi import HTTPException
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.session import SessionLocal
from app.mcp import tools as impl
from app.mcp.context import current_db, current_user
from app.mcp.jsonutil import json_safe
from app.models.domain import (
    GoalCategory,
    GoalVisibility,
    TargetDirection,
    TrackingType,
)
from app.schemas.domain import CheckinUpdate, GoalCreate
from app.services.mcp_tokens import authenticate as authenticate_mcp_token
from app.services.oauth import origin_from_headers, www_authenticate

INSTRUCTIONS = """\
You are connected to LockIn, a private team accountability app.
LockIn is the source of truth. You coach; you do not invent numbers.

Use get_team_standings and get_member_progress to compare teammates and
motivate the caller. Private goals are redacted: never mention a title,
description, target or value you were not given. Aggregates still include
private goals.

Before log_checkin, call get_my_goals and get_my_checkin so you use real
goal ids and the challenge's today. Only the caller can be checked in.

Use add_goal only for the caller and only before their commitment locks; it
fails once goals are locked. It skips the goal wizard's review step, so before
you call it confirm with them: the title, the tracking type and starting
point, whether the goal is required or optional (required goals decide the
forfeit, and it defaults to required), and whether it is TEAM-visible or
PRIVATE. Do not edit existing goals or change locked targets.
"""


def _http_message(exc: HTTPException) -> str:
    detail = exc.detail
    if isinstance(detail, dict):
        return str(detail.get("message") or detail.get("code") or detail)
    return str(detail)


def _validation_message(exc: ValidationError) -> str:
    return "; ".join(
        f"{'.'.join(str(part) for part in error['loc']) or 'goal'}: {error['msg']}"
        for error in exc.errors()
    )


def _run(fn: Callable[..., Any], **kwargs: Any) -> Any:
    try:
        result = fn(current_db.get(), current_user.get(), **kwargs)
    except HTTPException as exc:
        raise ToolError(_http_message(exc)) from exc
    return json_safe(result)


mcp = MCPServer(
    "LockIn",
    instructions=INSTRUCTIONS,
    version="0.1.0",
)


@mcp.tool()
def get_context() -> dict:
    """Who the caller is, the current challenge, their progress and streak."""
    return _run(impl.get_context)


@mcp.tool()
def get_my_goals() -> dict:
    """The caller's full goal tree, including private goals."""
    return _run(impl.get_my_goals)


@mcp.tool()
def get_team_standings() -> dict:
    """Every teammate's headline progress, streak and whether they checked in today.

    Sorted by progress. No goal titles.
    """
    return _run(impl.get_team_standings)


@mcp.tool()
def get_member_progress(
    user_id: str | None = None, display_name: str | None = None
) -> dict:
    """One member's goals and heatmap. Private goals are redacted unless it is you."""
    parsed = None
    if user_id:
        try:
            from uuid import UUID

            parsed = UUID(user_id)
        except ValueError as exc:
            raise ToolError("user_id must be a UUID") from exc
    return _run(impl.get_member_progress, user_id=parsed, display_name=display_name)


@mcp.tool()
def get_activity(limit: int = 50) -> list[dict]:
    """Recent team-visible check-in updates. Private entries are hidden."""
    return _run(impl.get_activity, limit=limit)


@mcp.tool()
def get_my_checkin(day: date | None = None) -> dict:
    """Today's (or a given day's) check-in form: existing note plus goals to update."""
    return _run(impl.get_my_checkin, day=day)


@mcp.tool()
def add_goal(
    category: GoalCategory,
    title: str,
    tracking_type: TrackingType,
    description: str | None = None,
    target_value: float | None = None,
    target_direction: TargetDirection | None = None,
    baseline_value: float | None = None,
    current_value: float | None = None,
    unit: str | None = None,
    manual_progress_percentage: int | None = None,
    visibility: GoalVisibility = GoalVisibility.TEAM,
    required: bool = True,
    parent_goal_id: str | None = None,
) -> dict:
    """Create a goal for the caller. Only works before the commitment is locked.

    Confirm the details with the caller first — this skips the goal wizard's
    review step.

    tracking_type picks what to fill in:
      MILESTONE  done / not done; leave the numeric fields empty.
      NUMERIC    needs target_value and target_direction (AT_LEAST / AT_MOST);
                 baseline_value defaults to current_value or 0.
      COUNT      needs a positive target_value; counts up from 0.
      MANUAL     a 0-100 manual_progress_percentage you set yourself.
    visibility TEAM (default) or PRIVATE. required defaults to true; required
    goals are the ones scored for the end-of-challenge forfeit. Pass
    parent_goal_id to nest one level under an existing goal (it inherits the
    parent's category).
    """
    try:
        payload = GoalCreate(
            category=category,
            title=title,
            tracking_type=tracking_type,
            description=description,
            target_value=target_value,
            target_direction=target_direction,
            baseline_value=baseline_value,
            current_value=current_value,
            unit=unit,
            manual_progress_percentage=manual_progress_percentage,
            visibility=visibility,
            required=required,
            parent_goal_id=parent_goal_id,
        )
    except ValidationError as exc:
        raise ToolError(_validation_message(exc)) from exc
    return _run(impl.add_goal, payload=payload)


@mcp.tool()
def log_checkin(
    day: date | None = None,
    note: str | None = None,
    updates: list[CheckinUpdate] | None = None,
) -> dict:
    """Log the caller's check-in for a day. Use goal ids from get_my_goals."""
    return _run(impl.log_checkin, day=day, note=note, updates=updates)


def _transport_security() -> TransportSecuritySettings:
    raw = get_settings().mcp_allowed_hosts.strip()
    if raw == "*":
        return TransportSecuritySettings(enable_dns_rebinding_protection=False)
    hosts: list[str] = []
    for host in raw.split(","):
        host = host.strip()
        if not host:
            continue
        hosts.append(host)
        if ":" not in host:
            hosts.append(f"{host}:*")
    return TransportSecuritySettings(allowed_hosts=hosts)


def build_mcp_asgi():
    """New Streamable HTTP app + session manager. Call once per process lifespan."""
    return mcp.streamable_http_app(
        streamable_http_path="/",
        stateless_http=True,
        transport_security=_transport_security(),
    )


class McpDispatchMiddleware:
    """Send /mcp and /mcp/* to the gateway before the SPA catch-all sees them.

    Starlette's Mount('/mcp') does not match POST /mcp (no trailing slash),
    which would otherwise 405 on the GET-only SPA route.
    """

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] == "http":
            path = scope.get("path", "")
            if path == "/mcp" or path.startswith("/mcp/"):
                rest = path[len("/mcp") :] or "/"
                scoped = dict(scope)
                scoped["path"] = rest
                scoped["root_path"] = scope.get("root_path", "") + "/mcp"
                await gateway(scoped, receive, send)
                return
        await self.app(scope, receive, send)


class McpGateway:
    """Bearer auth, then the current Streamable HTTP app.

    The inner app is rebuilt on each lifespan enter because the session
    manager can only be started once per instance.
    """

    def __init__(self) -> None:
        self._app = None

    def set_app(self, app) -> None:
        self._app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            if self._app is not None:
                await self._app(scope, receive, send)
            return
        headers = {
            key.decode(): value.decode() for key, value in scope.get("headers", [])
        }
        authorization = headers.get("authorization", "")
        if not authorization.lower().startswith("bearer "):
            await _send_json(
                send,
                401,
                "Not authenticated",
                extra_headers=_auth_challenge(headers),
            )
            return
        session: Session = SessionLocal()
        user_token = None
        db_token = None
        try:
            user = authenticate_mcp_token(
                session, authorization.split(" ", 1)[1].strip()
            )
            if user is None:
                await _send_json(
                    send,
                    401,
                    "Invalid token",
                    extra_headers=_auth_challenge(headers),
                )
                return
            user_token = current_user.set(user)
            db_token = current_db.set(session)
            if self._app is None:
                await _send_json(send, 503, "MCP is not ready")
                return
            await self._app(scope, receive, send)
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            if user_token is not None:
                current_user.reset(user_token)
            if db_token is not None:
                current_db.reset(db_token)
            session.close()


def _auth_challenge(headers: dict[str, str]) -> list[tuple[bytes, bytes]]:
    return [
        (b"www-authenticate", www_authenticate(origin_from_headers(headers)).encode()),
        (b"access-control-allow-origin", b"*"),
    ]


async def _send_json(
    send,
    status_code: int,
    detail: str,
    extra_headers: list[tuple[bytes, bytes]] | None = None,
) -> None:
    body = json.dumps({"detail": detail}).encode()
    await send(
        {
            "type": "http.response.start",
            "status": status_code,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
                *(extra_headers or []),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


gateway = McpGateway()
