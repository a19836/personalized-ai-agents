from __future__ import annotations

import asyncio
from typing import Annotated, Any

import httpx
from fastapi import FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from flask import Request, Response as FlaskResponse

from shared.auth import (
    AuthenticatedUser,
    AuthenticationError,
    authenticate_request_token,
    describe_token,
    extract_bearer_token,
)
from shared.http import parse_json_request
from shared.config import get_settings
from shared.logging import get_logger

logger = get_logger(__name__)

_SKIPPED_RESPONSE_HEADERS = {"content-length", "content-type"}

AuthorizationHeader = Annotated[
    str | None,
    Header(alias="Authorization", description="Firebase bearer token."),
]


def add_cors_middleware(app: FastAPI, allow_methods: list[str]) -> None:
    """Attach CORSMiddleware to a FastAPI app using the FRONTEND_ORIGIN env var."""
    frontend_origin = get_settings().frontend_origin
    allowed_origins = ["*"] if frontend_origin == "*" else [frontend_origin]
    cast_app: Any = app
    cast_app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=False,
        allow_methods=allow_methods,
        allow_headers=["Authorization", "Content-Type"],
    )


def get_authenticated_user(authorization: AuthorizationHeader = None) -> AuthenticatedUser:
    token = extract_bearer_token(authorization)
    try:
        return authenticate_request_token(token)
    except AuthenticationError as exc:
        logger.warning(
            "Unauthorized request token=%s error=%s",
            describe_token(token),
            exc,
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


def run_fastapi_as_cloud_function(app: FastAPI, request: Request) -> FlaskResponse:
    return asyncio.run(dispatch_fastapi_request(app, request))


async def dispatch_fastapi_request(app: FastAPI, request: Request) -> FlaskResponse:
    query_string = request.query_string.decode("utf-8")
    path = request.path or "/"
    target = f"{path}?{query_string}" if query_string else path
    headers = {key: value for key, value in request.headers.items() if key.lower() != "host"}
    body = build_forwarded_body(request)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url=f"{request.scheme}://{request.host}",
    ) as client:
        response = await client.request(
            method=request.method,
            url=target,
            headers=headers,
            **body,
        )

    flask_response = FlaskResponse(
        response.content,
        status=response.status_code,
        content_type=response.headers.get("content-type"),
    )
    for header, value in response.headers.multi_items():
        if header.lower() not in _SKIPPED_RESPONSE_HEADERS:
            flask_response.headers.add(header, value)
    return flask_response


def build_forwarded_body(request: Request) -> dict[str, Any]:
    parsed = parse_json_request(request)
    if parsed is not None:
        return {"json": parsed}

    raw_body = request.get_data()
    if not raw_body:
        return {}

    return {"content": raw_body}
