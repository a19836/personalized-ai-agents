from __future__ import annotations

import unittest
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any, cast

from flask import Flask, Response as FlaskResponse, request as flask_request
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.users_service.main import (  # noqa: E402
    app,
    get_authenticated_user,
    get_users_service,
    users_service,
)
from services.users_service.models import UserProfileUpdateRequest  # noqa: E402
from shared.auth import AuthenticatedUser  # noqa: E402


class StubUsersService:
    def __init__(self) -> None:
        now = datetime.now(timezone.utc)
        self.profile = {
            "uid": "user-123",
            "email": "user@example.com",
            "display_name": "Jane Doe",
            "role": "editor",
            "preferences": {"theme": "dark"},
            "created_at": now,
            "updated_at": now,
            "disabled": False,
        }
        self.users = [
            {
                "uid": "user-123",
                "email": "user@example.com",
                "display_name": "Jane Doe",
                "role": "editor",
                "preferences": {"theme": "dark"},
                "created_at": now,
                "updated_at": now,
                "disabled": False,
            },
            {
                "uid": "user-456",
                "email": "second@example.com",
                "display_name": "Second User",
                "role": "reader",
                "preferences": {"theme": "light"},
                "created_at": now,
                "updated_at": now,
                "disabled": False,
            },
        ]

    def get_current_user_profile(self, user: AuthenticatedUser) -> dict[str, Any]:
        return {**self.profile, "uid": user.uid, "email": user.email}

    def update_current_user_profile(
        self, user: AuthenticatedUser, payload: UserProfileUpdateRequest
    ) -> dict[str, Any]:
        data = {
            **self.profile,
            **payload.model_dump(exclude_unset=True),
            "uid": user.uid,
            "email": user.email,
        }
        return data

    def update_current_user_password(self, user: AuthenticatedUser, new_password: str) -> dict[str, str]:
        del user
        if new_password == "weak":
            raise ValueError("Password must be at least 6 characters")
        return {"message": "Password updated"}

    def list_users(self) -> list[dict[str, Any]]:
        return self.users

    def create_user(self, payload: Any) -> dict[str, Any]:
        data = payload.model_dump()
        created = {
            "uid": "user-789",
            "email": data["email"],
            "display_name": data.get("display_name"),
            "role": data.get("role"),
            "preferences": data.get("preferences"),
            "created_at": self.profile["created_at"],
            "updated_at": self.profile["updated_at"],
            "disabled": False,
        }
        self.users.append(created)
        return created

    def get_user(self, uid: str) -> dict[str, Any]:
        for item in self.users:
            if item["uid"] == uid:
                return item
        raise ValueError("User not found")

    def update_user(self, uid: str, payload: UserProfileUpdateRequest) -> dict[str, Any]:
        updates = payload.model_dump(exclude_unset=True)
        for index, item in enumerate(self.users):
            if item["uid"] != uid:
                continue
            self.users[index] = {**item, **updates}
            return self.users[index]
        raise ValueError("User not found")

    def delete_user(self, uid: str) -> dict[str, str]:
        for item in self.users:
            if item["uid"] != uid:
                continue
            self.users = [row for row in self.users if row["uid"] != uid]
            return {"message": "User deleted"}
        raise ValueError("User not found")


class UsersServiceFastAPITest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._original_overrides = app.dependency_overrides.copy()
        app.dependency_overrides[get_authenticated_user] = lambda: AuthenticatedUser(
            uid="user-123",
            email="user@example.com",
            claims={},
        )
        app.dependency_overrides[get_users_service] = lambda: StubUsersService()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls) -> None:
        app.dependency_overrides = cls._original_overrides

    def test_healthz_endpoint(self) -> None:
        response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_get_me_endpoint(self) -> None:
        response = self.client.get("/me")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["uid"], "user-123")

    def test_put_me_endpoint(self) -> None:
        response = self.client.put(
            "/me",
            json={"display_name": "John Doe", "preferences": {"theme": "light"}},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["display_name"], "John Doe")

    def test_put_me_accepts_stringified_json_body(self) -> None:
        response = self.client.put(
            "/me",
            json='{"display_name":"John Doe","preferences":{"theme":"light"}}',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["display_name"], "John Doe")

    def test_post_me_password_endpoint(self) -> None:
        response = self.client.post("/me/password", json={"new_password": "NewStrongPass123!"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["message"], "Password updated")

    def test_post_me_password_returns_bad_request_on_invalid_password(self) -> None:
        response = self.client.post("/me/password", json={"new_password": "weak"})
        self.assertEqual(response.status_code, 422)

    def test_list_users_endpoint(self) -> None:
        response = self.client.get("/users")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 2)
        self.assertEqual(response.json()[0]["uid"], "user-123")

    def test_post_users_endpoint(self) -> None:
        response = self.client.post(
            "/users",
            json={
                "email": "new.user@example.com",
                "password": "NewStrongPass123!",
                "display_name": "New User",
                "role": "reader",
                "preferences": {"theme": "dark"},
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["uid"], "user-789")
        self.assertEqual(response.json()["email"], "new.user@example.com")

    def test_post_users_endpoint_rejects_weak_password(self) -> None:
        response = self.client.post(
            "/users",
            json={
                "email": "new.user@example.com",
                "password": "weakpass",
                "display_name": "New User",
            },
        )
        self.assertEqual(response.status_code, 422)

    def test_get_user_endpoint(self) -> None:
        response = self.client.get("/users/user-456")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["email"], "second@example.com")

    def test_put_user_endpoint(self) -> None:
        response = self.client.put("/users/user-456", json={"role": "admin"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["role"], "admin")

    def test_delete_user_endpoint(self) -> None:
        response = self.client.delete("/users/user-456")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["message"], "User deleted")

    def test_unknown_profile_path_returns_not_found(self) -> None:
        response = self.client.get("/someone-else")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Not found")

    def test_cloud_function_entrypoint_bridges_to_fastapi(self) -> None:
        flask_app = Flask(__name__)
        with flask_app.test_request_context("/healthz", method="GET"):
            response = users_service(cast(Any, flask_request)._get_current_object())
        self.assertIsInstance(response, FlaskResponse)
        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
