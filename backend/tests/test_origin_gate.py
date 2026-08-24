"""Direct hits to the Cloud Run hostname must not serve the SPA."""

import importlib

import pytest
from fastapi.testclient import TestClient

RUN_APP = "lockin-979991728317.europe-west2.run.app"
CUSTOM = "lockin.talhaakhoon.dev"


@pytest.fixture
def production_origin_client(monkeypatch) -> TestClient:
    from app import config, main

    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("PUBLIC_ORIGIN", f"https://{CUSTOM}")
    config.get_settings.cache_clear()
    reloaded = importlib.reload(main)
    try:
        with TestClient(reloaded.app) as client:
            yield client
    finally:
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        monkeypatch.delenv("PUBLIC_ORIGIN", raising=False)
        config.get_settings.cache_clear()
        importlib.reload(main)


def test_a_direct_run_app_hit_is_a_cheap_404(production_origin_client) -> None:
    response = production_origin_client.get("/dashboard", headers={"host": RUN_APP})

    assert response.status_code == 404
    assert "text/html" not in response.headers["content-type"]


def test_the_worker_forwarded_host_still_serves_the_app(
    production_origin_client,
) -> None:
    response = production_origin_client.get(
        "/dashboard",
        headers={"host": RUN_APP, "x-forwarded-host": CUSTOM},
    )

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_the_liveness_probe_is_not_gated(production_origin_client) -> None:
    response = production_origin_client.get("/healthz", headers={"host": RUN_APP})

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_direct_run_app_mcp_is_also_blocked(production_origin_client) -> None:
    response = production_origin_client.post("/mcp", headers={"host": RUN_APP})

    assert response.status_code == 404
