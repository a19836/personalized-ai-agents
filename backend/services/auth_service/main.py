from __future__ import annotations

import os
from typing import Annotated, Any, cast

import functions_framework
from fastapi import Body, Depends, FastAPI, HTTPException, Response, status
from flask import Request, Response as FlaskResponse
from pydantic import ValidationError

from services.auth_service.models import LoginRequest, LoginResponse
from services.auth_service.service import AuthService, AuthenticationError
from shared.config import get_settings
from shared.fastapi import add_cors_middleware, run_fastapi_as_cloud_function
from shared.http import normalize_json_payload
from shared.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)

LoginPayload = Annotated[
    LoginRequest | str,
    Body(description="Email/password credentials for Firebase Authentication."),
]

app = FastAPI(
    title="Auth Service",
    summary="Authenticate users with Firebase email/password login.",
    description="Typed API for logging users in and returning Firebase tokens.",
    version="1.0.0",
)
add_cors_middleware(app, allow_methods=["GET", "POST", "OPTIONS"])


def get_auth_service() -> AuthService:
    return AuthService(settings=get_settings())


@app.get("/healthz", tags=["System"], summary="Check service health")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.options("/", include_in_schema=False)
@app.options("/{path:path}", include_in_schema=False)
def options_handler(path: str = "") -> Response:
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post(
    "/login",
    response_model=LoginResponse,
    tags=["Auth"],
    summary="Log in a user",
    description="Authenticate with Firebase using email and password.",
)
def login(
    payload: LoginPayload,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> LoginResponse:
    parsed_payload = _parse_login_payload(payload)
    logger.debug("Login attempt email=%s", parsed_payload.email)
    try:
        result = service.login_with_password(
            email=parsed_payload.email,
            password=parsed_payload.password,
        )
    except AuthenticationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    response = LoginResponse.model_validate(result)
    logger.info("Login successful uid=%s email=%s", response.uid, response.email)
    return response


@app.post(
    "/logout",
    tags=["Auth"],
    summary="Log out a user",
    description="Client-side logout acknowledgement endpoint.",
)
def logout() -> dict[str, str]:
    return {"message": "Logged out"}


@functions_framework.http
def auth_service(request: Request) -> FlaskResponse:
    logger.debug(
        "Auth service request method=%s path=%s",
        request.method.upper(),
        request.path.rstrip("/") or "/",
    )
    return run_fastapi_as_cloud_function(app, request)


def _parse_login_payload(payload: LoginRequest | str) -> LoginRequest:
    normalized = normalize_json_payload(payload)
    try:
        return LoginRequest.model_validate(normalized)
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.errors()) from exc

# Force rebuild: qua 26 ago 2026 18:02:46 WEST
