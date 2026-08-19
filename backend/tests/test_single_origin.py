"""One container serves the SPA and the API, so the split between them matters.

A client asking for a route that does not exist must be told that, rather than
handed the app shell with a 200 on it.
"""

import importlib

import pytest
from fastapi.testclient import TestClient


def test_the_liveness_probe_does_not_need_a_database(anon) -> None:
    response = anon.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_a_client_side_route_is_served_the_app_shell(anon) -> None:
    response = anon.get("/dashboard")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


@pytest.mark.parametrize(
    "path",
    [
        "/api",
        "/api/",
        "/api/v1/nope",
        "/api/v2/goals",
        "/oauth",
        "/oauth/nope",
        "/.well-known/nope",
    ],
)
def test_an_unknown_api_route_is_a_404_not_the_app_shell(anon, path) -> None:
    response = anon.get(path)

    assert response.status_code == 404
    assert "text/html" not in response.headers["content-type"]


def test_a_known_api_route_still_answers(anon) -> None:
    assert anon.get("/api/v1/health").json() == {"status": "ok"}


@pytest.fixture
def production_client(monkeypatch) -> TestClient:
    """The app as it is built when ENVIRONMENT=production."""
    from app import config, main

    monkeypatch.setenv("ENVIRONMENT", "production")
    config.get_settings.cache_clear()
    reloaded = importlib.reload(main)
    try:
        with TestClient(reloaded.app) as client:
            yield client
    finally:
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        config.get_settings.cache_clear()
        importlib.reload(main)


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_the_schema_is_not_reachable_in_production(production_client, path) -> None:
    response = production_client.get(path)

    assert response.status_code == 404
    assert "text/html" not in response.headers["content-type"]


def test_the_spa_is_still_served_in_production(production_client) -> None:
    assert production_client.get("/dashboard").status_code == 200


def test_built_public_files_are_served_as_themselves(tmp_path, monkeypatch) -> None:
    """The service worker and manifest must not fall through to index.html."""
    import importlib

    from app import config, main

    (tmp_path / "sw.js").write_text("// lockin-sw\nself.skipWaiting()\n")
    (tmp_path / "manifest.json").write_text('{"short_name":"LockIn"}')
    (tmp_path / "index.html").write_text('<div id="root"></div>')
    monkeypatch.setenv("FRONTEND_DIST", str(tmp_path))
    config.get_settings.cache_clear()
    reloaded = importlib.reload(main)
    try:
        with TestClient(reloaded.app) as client:
            worker = client.get("/sw.js")
            assert worker.status_code == 200
            assert "lockin-sw" in worker.text
            assert "javascript" in worker.headers["content-type"]
            assert worker.headers.get("service-worker-allowed") == "/"

            head = client.head("/sw.js")
            assert head.status_code == 200
            assert "javascript" in head.headers["content-type"]

            manifest = client.get("/manifest.json")
            assert manifest.status_code == 200
            assert manifest.json()["short_name"] == "LockIn"

            shell = client.get("/dashboard")
            assert shell.status_code == 200
            assert 'id="root"' in shell.text or "id='root'" in shell.text
    finally:
        monkeypatch.delenv("FRONTEND_DIST", raising=False)
        config.get_settings.cache_clear()
        importlib.reload(main)


def test_the_schema_is_reachable_outside_production(anon) -> None:
    assert anon.get("/openapi.json").status_code == 200
