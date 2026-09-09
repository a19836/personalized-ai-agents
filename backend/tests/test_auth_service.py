from __future__ import annotations

import unittest
from pathlib import Path
import sys
from typing import Any, cast

from flask import Flask, Response as FlaskResponse, request as flask_request
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.auth_service.main import app, auth_service, get_auth_service  # noqa: E402
from services.auth_service.service import AuthenticationError  # noqa: E402
from shared.config import get_settings  # noqa: E402


class StubAuthService:
    def login_with_password(self, email: str, password: str) -> dict[str, str | None]:
        if password == "bad-password":
            raise AuthenticationError("Invalid email or password")
        return {
            "id_token": "token-123",
            "refresh_token": "refresh-123",
            "uid": "user-123",
            "email": email,
        }


class AuthServiceFastAPITest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        settings = get_settings()
        cls.test_email = settings.test_email or ""
        cls.test_password = settings.test_password or ""
        cls._original_overrides = app.dependency_overrides.copy()
        app.dependency_overrides[get_auth_service] = lambda: StubAuthService()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls) -> None:
        app.dependency_overrides = cls._original_overrides

    def _require_test_credentials(self) -> None:
        if not self.test_email or not self.test_password:
            self.skipTest("TEST_EMAIL/TEST_PASSWORD not set")

    def test_healthz_endpoint(self) -> None:
        response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_login_endpoint(self) -> None:
        self._require_test_credentials()
        response = self.client.post(
            "/login",
            json={"email": self.test_email, "password": self.test_password},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["uid"], "user-123")
        self.assertEqual(response.json()["email"], self.test_email)

    def test_login_endpoint_accepts_stringified_json_body(self) -> None:
        self._require_test_credentials()
        response = self.client.post(
            "/login",
            json=f'{{"email":"{self.test_email}","password":"{self.test_password}"}}',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["email"], self.test_email)

    def test_login_returns_unauthorized_for_auth_errors(self) -> None:
        self._require_test_credentials()
        response = self.client.post(
            "/login",
            json={"email": self.test_email, "password": "bad-password"},
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "Invalid email or password")

    def test_logout_endpoint(self) -> None:
        response = self.client.post("/logout")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"message": "Logged out"})

    def test_cloud_function_entrypoint_bridges_to_fastapi(self) -> None:
        flask_app = Flask(__name__)
        with flask_app.test_request_context("/healthz", method="GET"):
            response = auth_service(cast(Any, flask_request)._get_current_object())
        self.assertIsInstance(response, FlaskResponse)
        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
