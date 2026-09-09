from __future__ import annotations

import json
import re
from typing import Any

from google import genai
from google.genai import types as genai_types

from ..service import AgentsService

SESSION_BEARER_TOKEN_KEY = "temp:bearer_token"
_JSON_OBJECT_RE = re.compile(r"{.*}", re.DOTALL)


def extract_json_object(raw_text: str) -> dict[str, Any] | None:
    text = raw_text.strip()
    if not text:
        return None
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].strip()
    candidate = text
    if not (candidate.startswith("{") and candidate.endswith("}")):
        match = _JSON_OBJECT_RE.search(candidate)
        if not match:
            return None
        candidate = match.group(0).strip()
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def extract_model_text(response: object) -> str:
    text = getattr(response, "text", None)
    if isinstance(text, str) and text.strip():
        return text.strip()
    candidates = getattr(response, "candidates", None)
    if isinstance(candidates, list):
        parts: list[str] = []
        for candidate in candidates:
            content = candidate.get("content") if isinstance(candidate, dict) else getattr(candidate, "content", None)
            candidate_parts = content.get("parts") if isinstance(content, dict) else getattr(content, "parts", None)
            if not isinstance(candidate_parts, list):
                continue
            for part in candidate_parts:
                part_text = part.get("text") if isinstance(part, dict) else getattr(part, "text", None)
                if isinstance(part_text, str) and part_text.strip():
                    parts.append(part_text.strip())
        if parts:
            return "\n".join(parts)
    return ""


def _normalize_tool_names(tool_names: list[str]) -> list[str]:
    normalized = [name.strip().lower() for name in tool_names if isinstance(name, str) and name.strip()]
    if not normalized:
        return []
    return normalized


def _build_direct_tools(tool_names: list[str]) -> list[Any]:
    direct_tools: list[Any] = []
    for name in _normalize_tool_names(tool_names):
        if name == "google_search":
            direct_tools.append(genai_types.GoogleSearch())
            continue
        if name == "url_context":
            direct_tools.append(genai_types.UrlContext())
            continue
        if name == "fetch_url_content":
            from .fetch_url_content import fetch_url_content

            direct_tools.append(fetch_url_content)
            continue
        raise ValueError(f"Unsupported tool name: {name}")
    return direct_tools


def _build_wrapped_tools(tool_names: list[str]) -> list[Any]:
    wrapped_tools: list[Any] = []
    for name in _normalize_tool_names(tool_names):
        if name == "google_search":
            wrapped_tools.append(genai_types.Tool(google_search=genai_types.GoogleSearch()))
            continue
        if name == "url_context":
            wrapped_tools.append(genai_types.Tool(url_context=genai_types.UrlContext()))
            continue
        if name == "fetch_url_content":
            from .fetch_url_content import fetch_url_content

            wrapped_tools.append(fetch_url_content)
            continue
        raise ValueError(f"Unsupported tool name: {name}")
    return wrapped_tools

def _build_tool_payload_variants(tool_names: list[str]) -> list[list[Any]]:
    # Some runtime SDK versions require Tool(...) wrappers; others accept direct tool instances.
    return [
        _build_wrapped_tools(tool_names),
        _build_direct_tools(tool_names),
    ]


def generate_content_with_tools(*, client: genai.Client, model: str, input_text: str, tool_names: list[str]) -> object:
    errors: list[str] = []
    last_exception: Exception | None = None
    if not (hasattr(client, "models") and hasattr(client.models, "generate_content")):
        raise RuntimeError("Gemini client does not expose models.generate_content.")
    for tools_payload in _build_tool_payload_variants(tool_names):
        try:
            config = genai_types.GenerateContentConfig(tools=tools_payload)
            return client.models.generate_content(model=model, contents=input_text, config=config)
        except Exception as exc:
            last_exception = exc
            errors.append(str(exc))
        try:
            config = genai_types.GenerateContentConfig(tools=tools_payload)
            return client.models.generate_content(model=model, contents=[input_text], config=config)
        except Exception as exc:
            last_exception = exc
            errors.append(str(exc))

    joined = " | ".join(errors)
    raise RuntimeError(f"Unable to create generate_content interaction: {joined}") from last_exception


def generate_content_with_url_context(*, client: genai.Client, model: str, prompt: str) -> object:
    return generate_content_with_tools(client=client, model=model, input_text=prompt, tool_names=["url_context"])


def service_from_context(default_service: AgentsService, tool_context: object | None) -> AgentsService:
    if tool_context is None:
        return default_service
    state = getattr(tool_context, "state", None)
    if state is None or not hasattr(state, "get"):
        return default_service
    token = state.get(SESSION_BEARER_TOKEN_KEY)
    if isinstance(token, str) and token.strip():
        return AgentsService(bearer_token=token.strip())
    return default_service
