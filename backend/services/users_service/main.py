from __future__ import annotations

from typing import Annotated, Any, cast

import functions_framework
from fastapi import Body, Depends, FastAPI, HTTPException, Path, Response, status
from flask import Request, Response as FlaskResponse
from pydantic import ValidationError

from services.users_service.models import (
    UserCreateRequest,
    UserPasswordUpdateRequest,
    UserPasswordUpdateResponse,
    UserProfileResponse,
    UserProfileUpdateRequest,
)
from services.users_service.repository import UserRepository
from services.users_service.service import UsersService
from shared.auth import AuthenticatedUser
from shared.fastapi import add_cors_middleware, get_authenticated_user, run_fastapi_as_cloud_function
from shared.http import normalize_json_payload
from shared.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)

ProfilePath = Annotated[
    str,
    Path(description="Profile route segment. Only 'me' is supported."),
]
UserIdPath = Annotated[
    str,
    Path(min_length=1, description="Target user identifier."),
]
ProfilePayload = Annotated[
    UserProfileUpdateRequest | str,
    Body(description="Fields to update on the current user profile."),
]
PasswordPayload = Annotated[
    UserPasswordUpdateRequest | str,
    Body(description="New password for the current authenticated user."),
]
CreateUserPayload = Annotated[
    UserCreateRequest | str,
    Body(description="New user details."),
]

app = FastAPI(
    title="Users Service",
    summary="Read and update the current authenticated user profile.",
    description="Typed API for loading and updating the current Firebase user's profile.",
    version="1.0.0",
)
add_cors_middleware(app, allow_methods=["GET", "PUT", "POST", "DELETE", "OPTIONS"])


def get_users_service() -> UsersService:
    return UsersService(repository=UserRepository())


@app.get("/healthz", tags=["System"], summary="Check service health")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.options("/", include_in_schema=False)
@app.options("/{path:path}", include_in_schema=False)
def options_handler(path: str = "") -> Response:
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get(
    "/me",
    response_model=UserProfileResponse,
    tags=["Users"],
    summary="Get current user profile",
    description="Return the current authenticated user's profile.",
)
def get_me(
    user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)],
    service: Annotated[UsersService, Depends(get_users_service)],
) -> UserProfileResponse:
    logger.debug("Fetching profile for uid=%s", user.uid)
    data = service.get_current_user_profile(user)
    response = UserProfileResponse.model_validate(data)
    logger.info("Returned profile for uid=%s", user.uid)
    return response


@app.get(
    "/users",
    response_model=list[UserProfileResponse],
    tags=["Users"],
    summary="List all users",
    description="Return all Firebase-authenticated users enriched with users collection profile data.",
)
def list_users(
    user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)],
    service: Annotated[UsersService, Depends(get_users_service)],
) -> list[UserProfileResponse]:
    del user
    return [UserProfileResponse.model_validate(item) for item in service.list_users()]


@app.post(
    "/users",
    response_model=UserProfileResponse,
    tags=["Users"],
    summary="Create new user",
    description="Create a new Firebase user and a users collection profile document.",
)
def create_user(
    payload: CreateUserPayload,
    user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)],
    service: Annotated[UsersService, Depends(get_users_service)],
) -> UserProfileResponse:
    del user
    parsed_payload = _parse_create_user_payload(payload)
    try:
        result = service.create_user(parsed_payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return UserProfileResponse.model_validate(result)


@app.get(
    "/users/{uid}",
    response_model=UserProfileResponse,
    tags=["Users"],
    summary="Get one user",
    description="Return one Firebase-authenticated user enriched with users collection profile data.",
)
def get_user(
    uid: UserIdPath,
    user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)],
    service: Annotated[UsersService, Depends(get_users_service)],
) -> UserProfileResponse:
    del user
    try:
        result = service.get_user(uid)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return UserProfileResponse.model_validate(result)


@app.put(
    "/me",
    response_model=UserProfileResponse,
    tags=["Users"],
    summary="Update current user profile",
    description="Update the current authenticated user's profile fields.",
)
def update_me(
    payload: ProfilePayload,
    user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)],
    service: Annotated[UsersService, Depends(get_users_service)],
) -> UserProfileResponse:
    parsed_payload = _parse_profile_payload(payload)
    logger.debug("Updating profile for uid=%s", user.uid)
    data = service.update_current_user_profile(user, parsed_payload)
    response = UserProfileResponse.model_validate(data)
    logger.info("Updated profile for uid=%s", user.uid)
    return response


@app.put(
    "/users/{uid}",
    response_model=UserProfileResponse,
    tags=["Users"],
    summary="Update one user",
    description="Update one user profile document by uid.",
)
def update_user(
    uid: UserIdPath,
    payload: ProfilePayload,
    user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)],
    service: Annotated[UsersService, Depends(get_users_service)],
) -> UserProfileResponse:
    del user
    parsed_payload = _parse_profile_payload(payload)
    try:
        result = service.update_user(uid, parsed_payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return UserProfileResponse.model_validate(result)


@app.post(
    "/me/password",
    response_model=UserPasswordUpdateResponse,
    tags=["Users"],
    summary="Update current user password",
    description="Update the current authenticated user's password.",
)
def update_me_password(
    payload: PasswordPayload,
    user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)],
    service: Annotated[UsersService, Depends(get_users_service)],
) -> UserPasswordUpdateResponse:
    parsed_payload = _parse_password_payload(payload)
    logger.debug("Updating password for uid=%s", user.uid)
    try:
        result = service.update_current_user_password(user, parsed_payload.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    logger.info("Updated password for uid=%s", user.uid)
    return UserPasswordUpdateResponse.model_validate(result)


@app.delete(
    "/users/{uid}",
    tags=["Users"],
    summary="Delete one user",
    description="Delete the target Firebase user and remove their users collection profile document.",
)
def delete_user(
    uid: UserIdPath,
    user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)],
    service: Annotated[UsersService, Depends(get_users_service)],
) -> dict[str, str]:
    del user
    try:
        return service.delete_user(uid)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@app.api_route(
    "/{profile_path}",
    methods=["GET", "PUT", "POST", "DELETE"],
    include_in_schema=False,
)
def reject_unknown_profile_path(profile_path: ProfilePath) -> None:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


@functions_framework.http
def users_service(request: Request) -> FlaskResponse:
    logger.debug(
        "Users service request method=%s path=%s",
        request.method.upper(),
        request.path.rstrip("/") or "/",
    )
    return run_fastapi_as_cloud_function(app, request)


def _parse_profile_payload(payload: UserProfileUpdateRequest | str) -> UserProfileUpdateRequest:
    normalized = normalize_json_payload(payload)
    try:
        return UserProfileUpdateRequest.model_validate(normalized)
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.errors()) from exc


def _parse_password_payload(payload: UserPasswordUpdateRequest | str) -> UserPasswordUpdateRequest:
    normalized = normalize_json_payload(payload)
    try:
        return UserPasswordUpdateRequest.model_validate(normalized)
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.errors()) from exc


def _parse_create_user_payload(payload: UserCreateRequest | str) -> UserCreateRequest:
    normalized = normalize_json_payload(payload)
    try:
        return UserCreateRequest.model_validate(normalized)
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.errors()) from exc
