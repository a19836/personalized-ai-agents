from __future__ import annotations

from dataclasses import dataclass

import httpx

from shared.config import Settings
from shared.logging import get_logger

logger = get_logger(__name__)


class AuthenticationError(Exception):
    pass


@dataclass
class AuthService:
    settings: Settings

    def login_with_password(self, email: str, password: str) -> dict[str, str | None]:
        if not self.settings.firebase_web_api_key:
            raise AuthenticationError(
                "FIREBASE_WEB_API_KEY is required for email/password login"
            )

        endpoint = (
            "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"
        )
        params = {"key": self.settings.firebase_web_api_key}
        payload = {
            "email": email,
            "password": password,
            "returnSecureToken": True,
        }
        logger.debug("Calling Firebase signInWithPassword for email=%s", email)
        try:
            response = httpx.post(endpoint, params=params, json=payload, timeout=10.0)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            message = "Invalid email or password"
            try:
                message = exc.response.json().get("error", {}).get("message") or message
            except Exception:
                pass
            raise AuthenticationError(message) from exc
        except httpx.HTTPError as exc:
            raise AuthenticationError("Could not reach Firebase Authentication") from exc

        data = response.json()
        logger.debug("Firebase login succeeded for uid=%s", data.get("localId"))
        return {
            "id_token": data["idToken"],
            "refresh_token": data.get("refreshToken"),
            "uid": data["localId"],
            "email": data["email"],
        }
