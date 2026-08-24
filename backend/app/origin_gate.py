"""Stop crawlers from billing Cloud Run on the public *.run.app URL.

The Cloudflare Worker already rewrites the request to the run.app origin and
sets X-Forwarded-Host to the custom domain. Direct hits to *.run.app do not,
so they get a cheap 404 instead of a billed SPA (and its /assets/* follow-ups).
/healthz stays open for the container probe.
"""

from __future__ import annotations

import json
from urllib.parse import urlparse

from app.config import get_settings

_NOT_FOUND = json.dumps({"detail": "Not found"}).encode()


class RunAppGateMiddleware:
    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] == "http" and _should_block(scope):
            await _send_not_found(send)
            return
        await self.app(scope, receive, send)


def _should_block(scope: dict) -> bool:
    path = scope.get("path", "")
    if path == "/healthz":
        return False
    settings = get_settings()
    if settings.environment != "production":
        return False
    expected = (urlparse(settings.public_origin).hostname or "").lower()
    if not expected:
        return False
    headers = {key.decode(): value.decode() for key, value in scope.get("headers", [])}
    host = headers.get("host", "").split(":")[0].lower()
    if not host.endswith(".run.app"):
        return False
    forwarded = headers.get("x-forwarded-host", "").split(",")[0].strip().split(":")[0]
    return forwarded.lower() != expected


async def _send_not_found(send) -> None:
    await send(
        {
            "type": "http.response.start",
            "status": 404,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(_NOT_FOUND)).encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": _NOT_FOUND})
