"""Web Push: VAPID keys, subscription storage, and best-effort delivery.

VAPID keys are derived from SECRET_KEY unless VAPID_PUBLIC_KEY and
VAPID_PRIVATE_KEY are set, so a deployed instance needs no extra secret.
Rotating SECRET_KEY mints a new pair and existing browser subscriptions stop
working until the member re-enables push.
"""

from __future__ import annotations

import json
import logging
import uuid
from functools import lru_cache

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from py_vapid import Vapid
from py_vapid.utils import b64urlencode
from pywebpush import WebPushException, webpush
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.domain import Notification, PushSubscription

logger = logging.getLogger(__name__)

# NIST P-256 curve order. A derived scalar must sit in (1, n-1).
_P256_N = 0xFFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551
_STALE = {404, 410}


def vapid_claims() -> dict[str, str]:
    """Fresh dict — pywebpush mutates `aud` and `exp` on the object we pass."""
    origin = get_settings().public_origin.strip()
    subject = origin if origin.startswith("https://") else "mailto:lockin@localhost"
    return {"sub": subject}


@lru_cache
def _derived_vapid(secret: str) -> Vapid:
    seed = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"lockin-web-push-vapid-v1",
        info=b"vapid",
    ).derive(secret.encode())
    scalar = int.from_bytes(seed, "big") % (_P256_N - 1) + 1
    return Vapid(private_key=ec.derive_private_key(scalar, ec.SECP256R1()))


def _override_vapid(public_key: str, private_key: str) -> Vapid:
    vapid = Vapid.from_string(private_key)
    expected = application_server_key(vapid)
    if expected != public_key:
        raise ValueError("VAPID_PUBLIC_KEY does not match VAPID_PRIVATE_KEY")
    return vapid


def vapid() -> Vapid:
    settings = get_settings()
    if settings.vapid_private_key and settings.vapid_public_key:
        return _override_vapid(settings.vapid_public_key, settings.vapid_private_key)
    return _derived_vapid(settings.secret_key)


def application_server_key(keys: Vapid | None = None) -> str:
    """URL-safe public key the browser's PushManager.subscribe() expects."""
    keys = keys or vapid()
    return b64urlencode(
        keys.public_key.public_bytes(
            serialization.Encoding.X962,
            serialization.PublicFormat.UncompressedPoint,
        )
    )


def config_payload() -> dict:
    return {"enabled": True, "public_key": application_server_key()}


def upsert(
    db: Session,
    *,
    user_id: uuid.UUID,
    endpoint: str,
    p256dh: str,
    auth: str,
    user_agent: str | None,
) -> PushSubscription:
    row = db.scalar(
        select(PushSubscription).where(PushSubscription.endpoint == endpoint)
    )
    if row:
        row.user_id = user_id
        row.p256dh = p256dh
        row.auth = auth
        row.user_agent = user_agent
        return row
    row = PushSubscription(
        user_id=user_id,
        endpoint=endpoint,
        p256dh=p256dh,
        auth=auth,
        user_agent=user_agent,
    )
    db.add(row)
    db.flush()
    return row


def remove(db: Session, *, user_id: uuid.UUID, endpoint: str) -> bool:
    row = db.scalar(
        select(PushSubscription).where(
            PushSubscription.user_id == user_id,
            PushSubscription.endpoint == endpoint,
        )
    )
    if not row:
        return False
    db.delete(row)
    return True


def public_row(row: PushSubscription) -> dict:
    return {"id": row.id, "endpoint": row.endpoint}


def deliver(db: Session, notification: Notification) -> None:
    """Best-effort: a failed push must never fail the action that triggered it."""
    try:
        _deliver(db, notification)
    except Exception:
        logger.exception("Web Push delivery failed")


def _deliver(db: Session, notification: Notification) -> None:
    rows = list(
        db.scalars(
            select(PushSubscription).where(
                PushSubscription.user_id == notification.user_id
            )
        )
    )
    if not rows:
        return
    payload = json.dumps(
        {
            "title": notification.title,
            "body": notification.body or "",
            "url": notification.link_path or "/",
            "tag": f"{notification.type.value}:{notification.dedupe_key}",
        }
    )
    keys = vapid()
    claims = vapid_claims()
    stale: list[PushSubscription] = []
    for row in rows:
        try:
            webpush(
                subscription_info={
                    "endpoint": row.endpoint,
                    "keys": {"p256dh": row.p256dh, "auth": row.auth},
                },
                data=payload,
                vapid_private_key=keys,
                vapid_claims=dict(claims),
                ttl=86400,
                timeout=8,
            )
        except WebPushException as exc:
            status = getattr(exc.response, "status_code", None)
            if status in _STALE:
                stale.append(row)
            else:
                logger.warning("Web Push rejected: %s", exc)
    for row in stale:
        db.delete(row)
