from __future__ import annotations

import json
from typing import Any

from flask import Request, jsonify
from shared.config import get_settings


def normalize_json_payload(value: Any) -> Any:
    if not isinstance(value, str):
        return value

    stripped = value.strip()
    if not stripped:
        return value

    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return value


def parse_json_request(request: Request) -> Any | None:
    if request.is_json:
        parsed = normalize_json_payload(request.get_json(silent=True))
        if parsed is not None:
            return parsed

    raw_body = request.get_data()
    if not raw_body:
        return None

    try:
        return normalize_json_payload(json.loads(raw_body.decode("utf-8")))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


def cors_headers() -> dict[str, str]:
    origin = get_settings().frontend_origin
    return {
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Headers": "Authorization, Content-Type",
        "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
        "Vary": "Origin",
    }


def json_response(payload: Any, status_code: int):
    response = jsonify(payload)
    response.status_code = status_code
    response.headers.update(cors_headers())
    return response
