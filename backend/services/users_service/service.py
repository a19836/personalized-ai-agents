from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from firebase_admin import _auth_utils
from firebase_admin import auth as firebase_auth

from services.users_service.models import UserCreateRequest, UserProfileUpdateRequest
from services.users_service.repository import UserRepository
from shared.auth import AuthenticatedUser
from shared.firebase import initialize_firebase
from shared.logging import get_logger

logger = get_logger(__name__)


@dataclass
class UsersService:
    repository: UserRepository

    def _merge_user_data(self, auth_user: Any, profile: dict | None) -> dict[str, Any]:
        return {
            "uid": auth_user.uid,
            "email": auth_user.email,
            "display_name": (profile or {}).get("display_name"),
            "role": (profile or {}).get("role"),
            "preferences": (profile or {}).get("preferences"),
            "created_at": (profile or {}).get("created_at"),
            "updated_at": (profile or {}).get("updated_at"),
            "disabled": bool(getattr(auth_user, "disabled", False)),
        }

    def create_user(self, payload: UserCreateRequest) -> dict[str, Any]:
        initialize_firebase()
        try:
            created = firebase_auth.create_user(
                email=payload.email,
                password=payload.password,
            )
        except _auth_utils.EmailAlreadyExistsError as exc:
            raise ValueError("Email already exists") from exc
        except _auth_utils.InvalidPasswordError as exc:
            raise ValueError("Password must be at least 6 characters") from exc
        except _auth_utils.FirebaseAuthError as exc:
            raise ValueError(str(exc)) from exc

        values = {
            "display_name": payload.display_name,
            "role": payload.role,
            "preferences": payload.preferences,
        }
        saved = self.repository.save(created.uid, values)
        auth_user = firebase_auth.get_user(created.uid)
        return self._merge_user_data(auth_user, saved)

    def list_users(self) -> list[dict[str, Any]]:
        initialize_firebase()
        profile_by_uid = {profile["uid"]: profile for profile in self.repository.list_all()}
        users: list[dict[str, Any]] = []
        for auth_user in firebase_auth.list_users().iterate_all():
            users.append(self._merge_user_data(auth_user, profile_by_uid.get(auth_user.uid)))
        users.sort(key=lambda item: item.get("email") or item["uid"])
        return users

    def get_user(self, uid: str) -> dict[str, Any]:
        initialize_firebase()
        try:
            auth_user = firebase_auth.get_user(uid)
        except _auth_utils.UserNotFoundError as exc:
            raise ValueError("User not found") from exc
        profile = self.repository.get(uid)
        return self._merge_user_data(auth_user, profile)

    def update_user(self, uid: str, payload: UserProfileUpdateRequest) -> dict[str, Any]:
        initialize_firebase()
        try:
            auth_user = firebase_auth.get_user(uid)
        except _auth_utils.UserNotFoundError as exc:
            raise ValueError("User not found") from exc
        values = payload.model_dump(exclude_unset=True)
        saved = self.repository.save(uid, values)
        return self._merge_user_data(auth_user, saved)

    def delete_user(self, uid: str) -> dict[str, str]:
        initialize_firebase()
        try:
            firebase_auth.delete_user(uid)
        except _auth_utils.UserNotFoundError as exc:
            raise ValueError("User not found") from exc
        self.repository.delete(uid)
        return {"message": "User deleted"}

    def get_current_user_profile(self, user: AuthenticatedUser) -> dict[str, Any]:
        logger.debug("Loading profile for uid=%s", user.uid)
        profile = self.repository.get(user.uid)
        if not profile:
            return {
                "uid": user.uid,
                "email": user.email,
                "display_name": None,
                "role": None,
                "preferences": None,
                "created_at": None,
                "updated_at": None,
                "disabled": None,
            }
        return {
            "uid": profile["uid"],
            "email": user.email,
            "display_name": profile.get("display_name"),
            "role": profile.get("role"),
            "preferences": profile.get("preferences"),
            "created_at": profile.get("created_at"),
            "updated_at": profile.get("updated_at"),
            "disabled": None,
        }

    def update_current_user_profile(
        self, user: AuthenticatedUser, payload: UserProfileUpdateRequest
    ) -> dict[str, Any]:
        logger.debug("Saving profile for uid=%s", user.uid)
        values = payload.model_dump(exclude_unset=True)
        saved = self.repository.save(user.uid, values)
        return {
            "uid": saved["uid"],
            "email": user.email,
            "display_name": saved.get("display_name"),
            "role": saved.get("role"),
            "preferences": saved.get("preferences"),
            "created_at": saved.get("created_at"),
            "updated_at": saved.get("updated_at"),
            "disabled": None,
        }

    def update_current_user_password(self, user: AuthenticatedUser, new_password: str) -> dict[str, str]:
        logger.debug("Updating password for uid=%s", user.uid)
        try:
            initialize_firebase()
            firebase_auth.update_user(uid=user.uid, password=new_password)
        except _auth_utils.UserNotFoundError as exc:
            raise ValueError("User not found") from exc
        except _auth_utils.InvalidPasswordError as exc:
            raise ValueError("Password must be at least 6 characters") from exc
        except _auth_utils.FirebaseAuthError as exc:
            raise ValueError(str(exc)) from exc
        return {"message": "Password updated"}
