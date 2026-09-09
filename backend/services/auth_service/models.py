from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr = Field(
        description="User email address used for Firebase Authentication.",
        examples=["test@test.com"],
    )
    password: str = Field(
        ...,
        min_length=1,
        description="Plain-text password for the user account.",
        examples=["testpassword123"],
    )


class LoginResponse(BaseModel):
    id_token: str = Field(description="Firebase ID token for authenticated requests.")
    refresh_token: str | None = Field(
        default=None,
        description="Firebase refresh token returned by the login flow.",
    )
    uid: str = Field(description="Firebase user identifier.")
    email: EmailStr = Field(description="Authenticated user email address.")
