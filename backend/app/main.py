from pathlib import Path

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import router
from app.config import get_settings

settings = get_settings()
production = settings.environment == "production"

# The schema browser is a map of every endpoint. Useful locally, needless
# surface area on a deployed instance.
app = FastAPI(
    title="LockIn API",
    version="0.1.0",
    docs_url=None if production else "/docs",
    redoc_url=None,
    openapi_url=None if production else "/openapi.json",
)
app.include_router(router, prefix="/api/v1")

# In production these are unregistered, so without this the SPA catch-all would
# answer them with the app shell and a 200 — a confusing "yes" to a schema request.
SCHEMA_PATHS = {"docs", "redoc", "openapi.json"} if production else set()

dist = Path(settings.frontend_dist).resolve()
assets = dist / "assets"
if assets.exists():
    app.mount("/assets", StaticFiles(directory=assets), name="assets")


@app.get("/healthz", include_in_schema=False)
def healthz() -> dict[str, str]:
    """Liveness probe for the container. Deliberately does not touch the database."""
    return {"status": "ok"}


@app.get("/{path:path}", include_in_schema=False)
def spa(path: str) -> FileResponse:
    """Serve the built SPA for client-side routes.

    Anything under the API prefix must 404 as an API rather than fall through to
    the app shell: a caller asking for a route that does not exist should be told
    so, not handed a page of HTML with a 200 on it.
    """
    if path == "api" or path.startswith("api/") or path in SCHEMA_PATHS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    index = dist / "index.html"
    if not index.exists():
        return FileResponse(Path(__file__).parent / "placeholder.html")
    return FileResponse(index)
