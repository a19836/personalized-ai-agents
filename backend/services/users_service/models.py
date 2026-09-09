from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field, field_validator


def _validate_secure_password(value: str) -> str:
    errors: list[str] = []
    if len(value) < 8:
        errors.append("at least 8 characters")
    if not re.search(r"[A-Z]", value):
        errors.append("one uppercase letter")
    if not re.search(r"[a-z]", value):
        errors.append("one lowercase letter")
    if not re.search(r"[0-9]", value):
        errors.append("one number")
    if not re.search(r"[^A-Za-z0-9]", value):
        errors.append("one special character")
    if errors:
        raise ValueError(f"Password must include {', '.join(errors)}.")
    return value


class UserProfileResponse(BaseModel):
    uid: str = Field(description="Firebase user identifier.")
    email: EmailStr | None = Field(default=None, description="Authenticated user email address.")
    display_name: str | None = Field(default=None, description="Display name shown in the UI.")
    role: str | None = Field(default=None, description="Optional application role for the user.")
    preferences: dict[str, Any] | None = Field(
        default=None,
        description="User-specific preferences stored as key/value pairs.",
    )
    created_at: datetime | None = Field(default=None, description="Timestamp when the profile was created.")
    updated_at: datetime | None = Field(default=None, description="Timestamp when the profile was last updated.")
    disabled: bool | None = Field(default=None, description="Whether the authentication user is disabled.")


class UserProfileUpdateRequest(BaseModel):
    display_name: str | None = Field(
        default=None,
        max_length=200,
        description="Display name shown in the UI.",
        examples=["Joao Pinto"],
    )
    role: str | None = Field(
        default=None,
        max_length=100,
        description="Optional application role for the user.",
        examples=["editor"],
    )
    preferences: dict[str, Any] | None = Field(
        default=None,
        description="User-specific preferences stored as key/value pairs.",
        examples=[{"theme": "dark"}],
    )


class UserPasswordUpdateRequest(BaseModel):
    new_password: str = Field(
        ...,
        min_length=8,
        description="New password for the authenticated user.",
        examples=["NewStrongPassword123!"],
    )

    @field_validator("new_password")
    @classmethod
    def validate_password_policy(cls, value: str) -> str:
        return _validate_secure_password(value)


class UserPasswordUpdateResponse(BaseModel):
    message: str = Field(description="Password update status message.")


class UserCreateRequest(BaseModel):
    email: EmailStr = Field(
        description="Email address for the new user.",
        examples=["new.user@example.com"],
    )
    password: str = Field(
        ...,
        min_length=8,
        description="Initial password for the new user.",
        examples=["NewStrongPassword123!"],
    )
    display_name: str | None = Field(
        default=None,
        max_length=200,
        description="Display name shown in the UI.",
        examples=["New User"],
    )
    role: str | None = Field(
        default=None,
        max_length=100,
        description="Optional application role for the user.",
        examples=["reader"],
    )
    preferences: dict[str, Any] | None = Field(
        default=None,
        description="User-specific preferences stored as key/value pairs.",
        examples=[{"theme": "dark"}],
    )

    @field_validator("password")
    @classmethod
    def validate_password_policy(cls, value: str) -> str:
        return _validate_secure_password(value)
