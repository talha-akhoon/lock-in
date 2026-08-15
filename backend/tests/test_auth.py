"""Google Sign-In, session cookies and CSRF."""

import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.config import get_settings
from app.dependencies.auth import CSRF_COOKIE, SESSION_COOKIE

GOOGLE_ENDPOINT = "/api/v1/auth/google"


@pytest.fixture
def google_configured(monkeypatch):
    monkeypatch.setattr(get_settings(), "google_client_id", "test-client-id")


@pytest.fixture
def verified_claims(monkeypatch):
    """Stand in for Google's tokeninfo call, which cannot run offline."""

    def fake_verify(token, request, audience):
        if token == "bad-token":
            raise ValueError("Invalid token")
        return {
            "sub": "google-sub-1",
            "email": "member@example.com",
            "email_verified": token != "unverified",
            "name": "New Member",
            "picture": "https://example.com/a.png",
        }

    monkeypatch.setattr(
        "app.api.v1.routes.auth.google_id_token.verify_oauth2_token", fake_verify
    )


def test_google_auth_creates_a_user_and_sets_both_cookies(
    anon, google_configured, verified_claims, db
) -> None:
    from app.models.domain import User

    response = anon.post(GOOGLE_ENDPOINT, json={"id_token": "good-token"})

    assert response.status_code == 200
    assert response.json()["user"]["email"] == "member@example.com"
    assert SESSION_COOKIE in response.cookies
    assert CSRF_COOKIE in response.cookies
    assert db.query(User).filter_by(google_sub="google-sub-1").one()


def test_google_auth_is_idempotent_for_a_returning_user(
    anon, google_configured, verified_claims, db
) -> None:
    from app.models.domain import User

    anon.post(GOOGLE_ENDPOINT, json={"id_token": "good-token"})
    anon.post(GOOGLE_ENDPOINT, json={"id_token": "good-token"})

    assert db.query(User).filter_by(google_sub="google-sub-1").count() == 1


def test_unverified_google_email_is_rejected(
    anon, google_configured, verified_claims
) -> None:
    response = anon.post(GOOGLE_ENDPOINT, json={"id_token": "unverified"})
    assert response.status_code == 401
    assert "not verified" in response.json()["detail"]


def test_invalid_google_token_is_rejected(
    anon, google_configured, verified_claims
) -> None:
    response = anon.post(GOOGLE_ENDPOINT, json={"id_token": "bad-token"})
    assert response.status_code == 401


def test_auth_is_unavailable_when_no_client_id_is_configured(anon, monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "google_client_id", "")
    response = anon.post(GOOGLE_ENDPOINT, json={"id_token": "good-token"})
    assert response.status_code == 503


def test_me_requires_a_session(anon) -> None:
    assert anon.get("/api/v1/auth/me").status_code == 401


def test_expired_session_is_rejected(anon, make_user) -> None:
    user = make_user()
    past = datetime.now(UTC) - timedelta(days=1)
    expired = jwt.encode(
        {"sub": str(user.id), "iat": past - timedelta(days=31), "exp": past},
        get_settings().secret_key,
        algorithm="HS256",
    )
    anon.cookies.set(SESSION_COOKIE, expired)
    assert anon.get("/api/v1/auth/me").status_code == 401


def test_session_signed_with_the_wrong_key_is_rejected(anon, make_user) -> None:
    user = make_user()
    now = datetime.now(UTC)
    forged = jwt.encode(
        {"sub": str(user.id), "iat": now, "exp": now + timedelta(days=1)},
        # Long enough that PyJWT does not warn about key length; the point of
        # the test is that it is the wrong key, not a weak one.
        "not-the-real-secret-but-long-enough-for-hs256",
        algorithm="HS256",
    )
    anon.cookies.set(SESSION_COOKIE, forged)
    assert anon.get("/api/v1/auth/me").status_code == 401


def test_session_for_a_deleted_user_is_rejected(anon, client_factory) -> None:
    client = client_factory(uuid.uuid4())
    assert client.get("/api/v1/auth/me").status_code == 401


def test_me_reports_team_and_challenge_context(team_setup) -> None:
    body = team_setup.admin_client.get("/api/v1/auth/me").json()

    assert body["team"]["name"] == "The Boys"
    assert body["role"] == "ADMIN"
    assert body["challenge_id"] == str(team_setup.challenge.id)
    assert body["challenge_status"] == "ACTIVE"
    assert body["goals_locked"] is False


def test_me_without_a_team_returns_no_team(client_factory, make_user) -> None:
    user = make_user()
    body = client_factory(user.id).get("/api/v1/auth/me").json()

    assert body["team"] is None
    assert body["challenge_id"] is None


def test_logout_clears_both_cookies(team_setup) -> None:
    response = team_setup.admin_client.post("/api/v1/auth/logout")

    assert response.status_code == 200
    for cookie in response.headers.get_list("set-cookie"):
        if SESSION_COOKIE in cookie or CSRF_COOKIE in cookie:
            assert "Max-Age=0" in cookie or "expires=Thu, 01 Jan 1970" in cookie.lower()


# ---------------------------------------------------------------------------
# CSRF: double-submit cookie
# ---------------------------------------------------------------------------


def test_post_without_a_csrf_header_is_rejected(client_factory, make_user) -> None:
    client = client_factory(make_user().id, csrf=False)
    response = client.post("/api/v1/teams", json={"name": "No CSRF"})
    assert response.status_code == 403


def test_post_with_a_mismatched_csrf_header_is_rejected(
    client_factory, make_user
) -> None:
    client = client_factory(make_user().id)
    response = client.post(
        "/api/v1/teams", json={"name": "Wrong"}, headers={"X-CSRF-Token": "different"}
    )
    assert response.status_code == 403


def test_post_without_a_csrf_cookie_is_rejected(client_factory, make_user) -> None:
    client = client_factory(make_user().id)
    client.cookies.delete(CSRF_COOKIE)
    response = client.post("/api/v1/teams", json={"name": "No cookie"})
    assert response.status_code == 403


def test_get_requests_are_exempt_from_csrf(client_factory, make_user) -> None:
    client = client_factory(make_user().id, csrf=False)
    assert client.get("/api/v1/auth/me").status_code == 200
