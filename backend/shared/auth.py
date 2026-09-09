from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any

from shared.firebase import verify_id_token
from shared.logging import get_logger

logger = get_logger(__name__)


class AuthenticationError(Exception):
    pass


@dataclass
class AuthenticatedUser:
    uid: str
    email: str | None
    claims: dict[str, Any]


def extract_bearer_token(value: str | None) -> str | None:
    if not value:
        return None
    parts = value.strip().split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    logger.debug("Extracted bearer token from Authorization header")
    return parts[1].strip()


def _decode_unverified_payload(token: str) -> dict[str, Any] | None:
    try:
        _, payload, _ = token.split(".")
        padding = "=" * (-len(payload) % 4)
        raw = base64.urlsafe_b64decode(payload + padding)
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return None


def describe_token(token: str | None) -> dict[str, Any]:
    if not token:
        return {"present": False}
    payload = _decode_unverified_payload(token)
    if not payload:
        return {
            "present": True,
            "length": len(token),
            "preview": f"{token[:12]}...{token[-8:]}" if len(token) > 20 else token,
        }
    return {
        "present": True,
        "length": len(token),
        "preview": f"{token[:12]}...{token[-8:]}" if len(token) > 20 else token,
        "uid": payload.get("user_id") or payload.get("sub"),
        "email": payload.get("email"),
        "aud": payload.get("aud"),
        "iss": payload.get("iss"),
        "exp": payload.get("exp"),
        "iat": payload.get("iat"),
    }


def authenticate_request_token(token: str | None) -> AuthenticatedUser:
    if not token:
        raise AuthenticationError("Missing Bearer token")

    try:
        logger.debug("Verifying token metadata=%s", describe_token(token))
        decoded = verify_id_token(token)
    except Exception as exc:
        logger.warning(
            "Token verification failed metadata=%s error=%s",
            describe_token(token),
            exc,
        )
        raise AuthenticationError("Invalid or expired token") from exc

    logger.debug(
        "Authenticated user uid=%s email=%s",
        decoded.get("uid"),
        decoded.get("email"),
    )
    return AuthenticatedUser(
        uid=decoded["uid"],
        email=decoded.get("email"),
        claims=decoded,
    )
