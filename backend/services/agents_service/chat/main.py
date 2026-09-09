from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
import logging
from typing import Annotated
import requests

from fastapi import APIRouter, Body, Depends, HTTPException, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ValidationError
from shared.auth import AuthenticatedUser
from shared.config import get_settings
from shared.fastapi import get_authenticated_user
from shared.http import normalize_json_payload
from shared.logging import resolve_log_level

from services.agents_service.admin.service import AgentManagementService
from services.agents_service.chat.models import (
    AgentChatMessage,
    AgentChatSessionCreateRequest,
    AgentChatSessionDetailResponse,
    AgentChatSessionResponse,
    ChatMessageRole,
)
from services.agents_service.chat.repository import AgentChatRepository
from services.agents_service.chat.service import AgentsService
from services.agents_service import main as core
from services.agents_service.admin.default_agents import build_articles_agent, build_users_agent
from services.agents_service.chat.tool_handlers.shared import SESSION_BEARER_TOKEN_KEY

router = APIRouter()


class AgentChatRequest(BaseModel):
    agent_id: str = Field(description="Which agent to use.")
    message: str = Field(min_length=1, description="User message to send to the selected agent.")
    model: str | None = Field(default=None, min_length=1, description="Optional model override.")
    session_id: str | None = Field(default=None, min_length=1, description="Optional persisted chat session id.")


def _run_gemini_query(uid: str, prompt: str, model: str) -> dict[str, str]:
    client = core.get_gemini_client()
    response = client.models.generate_content(model=model, contents=prompt)
    text = (response.text or "").strip() or "Gemini returned no text."
    return {
        "agent_id": core.AGENT_GEMINI,
        "model": model,
        "message": prompt,
        "response": text,
    }


def _run_gpt_query(uid: str, prompt: str, model: str, agent_id: str = core.AGENT_GPT) -> dict[str, str]:
    del uid
    settings = get_settings()
    openai_api_key = (settings.openai_api_key or "").strip()
    if not openai_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OPENAI_API_KEY is required to call GPT models.",
        )

    openai_base_url = settings.openai_base_url
    try:
        response = requests.post(
            f"{openai_base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {openai_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=30,
        )
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to call GPT model endpoint: {exc}",
        ) from exc

    try:
        payload = response.json() if response.content else {}
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="GPT model endpoint returned invalid JSON.",
        ) from exc

    if not response.ok:
        detail = ""
        if isinstance(payload, dict):
            error = payload.get("error")
            if isinstance(error, dict):
                message = error.get("message")
                if isinstance(message, str):
                    detail = message
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=detail or f"GPT model endpoint failed with status {response.status_code}.",
        )

    choices = payload.get("choices") if isinstance(payload, dict) else None
    if not isinstance(choices, list) or not choices:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="GPT model endpoint returned no choices.",
        )

    first_choice = choices[0]
    message = first_choice.get("message") if isinstance(first_choice, dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str) or not content.strip():
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="GPT model endpoint returned no text response.",
        )

    return {
        "agent_id": agent_id,
        "model": model,
        "message": prompt,
        "response": content.strip(),
    }


def _run_article_agent_query(uid: str, message: str, service: AgentsService) -> dict[str, str]:
    return _run_adk_agent_query(
        uid=uid,
        message=message,
        agent_id=core.AGENT_ARTICLE,
        app_name=core.AGENT_ARTICLE,
        agent=build_articles_agent(service),
        bearer_token=service.bearer_token,
    )


def _run_users_agent_query(uid: str, message: str, service: AgentsService) -> dict[str, str]:
    return _run_adk_agent_query(
        uid=uid,
        message=message,
        agent_id=core.AGENT_USERS,
        app_name=core.AGENT_USERS,
        agent=build_users_agent(service),
        bearer_token=service.bearer_token,
    )


def _run_adk_agent_query(
    uid: str,
    message: str,
    agent_id: str,
    app_name: str,
    agent: object,
    bearer_token: str,
) -> dict[str, str]:
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types as genai_types

    session_service = InMemorySessionService()
    session_state = {SESSION_BEARER_TOKEN_KEY: bearer_token}
    try:
        session = session_service.create_session(
            app_name=app_name,
            user_id=uid,
            state=session_state,
        )
    except TypeError:
        session = session_service.create_session(app_name=app_name, user_id=uid)
    if asyncio.iscoroutine(session):
        session = asyncio.run(session)
    state = getattr(session, "state", None)
    if isinstance(state, dict):
        state.setdefault(SESSION_BEARER_TOKEN_KEY, bearer_token)
    runner = Runner(agent=agent, app_name=app_name, session_service=session_service)

    new_message = genai_types.Content(role="user", parts=[genai_types.Part(text=message)])
    result_text = ""
    for event in runner.run(user_id=uid, session_id=session.id, new_message=new_message):
        if event.content and event.content.role == "model" and event.content.parts:
            for part in event.content.parts:
                if hasattr(part, "text") and part.text:
                    result_text += part.text

    return {
        "agent_id": agent_id,
        "message": message,
        "response": result_text.strip() or "Agent returned no response.",
    }


def _get_remote_agent_resource_name(agent_id: str) -> str | None:
    settings = get_settings()
    if agent_id == core.AGENT_ARTICLE:
        return (settings.articles_agent_engine or "").strip() or None
    if agent_id == core.AGENT_USERS:
        return (settings.users_agent_engine or "").strip() or None
    return None


def _resource_location(resource_name: str) -> str:
    parts = resource_name.split("/")
    if "locations" in parts:
        idx = parts.index("locations")
        if idx + 1 < len(parts):
            return parts[idx + 1]
    return "us-central1"


def _extract_session_id(session_obj: object) -> str | None:
    if session_obj is None:
        return None
    if isinstance(session_obj, dict):
        value = session_obj.get("id")
        if isinstance(value, str) and value:
            return value
        return None
    value = getattr(session_obj, "id", None)
    if isinstance(value, str) and value:
        return value
    return None


def _extract_deployed_agent_text(payload: object) -> str:
    if isinstance(payload, str):
        return payload.strip()
    if hasattr(payload, "text") and isinstance(getattr(payload, "text"), str):
        return getattr(payload, "text").strip()

    def _parts_text(parts: object) -> str:
        if not isinstance(parts, list):
            return ""
        chunks: list[str] = []
        for part in parts:
            if isinstance(part, dict):
                value = part.get("text")
            else:
                value = getattr(part, "text", None)
            if isinstance(value, str) and value.strip():
                chunks.append(value.strip())
        return "\n".join(chunks).strip()

    if isinstance(payload, dict):
        for key in ("response", "text", "output", "result"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        content = payload.get("content")
        if isinstance(content, dict):
            text = _parts_text(content.get("parts"))
            if text:
                return text
        return ""

    content = getattr(payload, "content", None)
    if content is not None:
        text = _parts_text(getattr(content, "parts", None))
        if text:
            return text
    return ""


def _extract_deployed_function_response(payload: object) -> object | None:
    responses = _collect_deployed_function_responses(payload)
    return responses[0] if responses else None


def _collect_deployed_function_responses(payload: object) -> list[object]:
    if isinstance(payload, dict):
        content = payload.get("content")
    else:
        content = getattr(payload, "content", None)
    if content is None:
        return []
    if isinstance(content, dict):
        parts = content.get("parts")
    else:
        parts = getattr(content, "parts", None)
    if not isinstance(parts, list):
        return []
    responses: list[object] = []
    for part in parts:
        if isinstance(part, dict):
            function_response = part.get("function_response") or part.get("functionResponse")
        else:
            function_response = getattr(part, "function_response", None) or getattr(part, "functionResponse", None)
        if not isinstance(function_response, dict) and not hasattr(function_response, "response"):
            continue
        if isinstance(function_response, dict) and "response" in function_response:
            responses.append(function_response["response"])
            continue
        response = getattr(function_response, "response", None)
        if response is not None:
            responses.append(response)
    return responses


def _extract_display_from_payload(payload: object, depth: int = 0) -> str:
    if depth > 12:
        return ""

    if isinstance(payload, str):
        return ""

    if isinstance(payload, dict):
        display_html = payload.get("display_html")
        if isinstance(display_html, str) and display_html.strip():
            return display_html.strip()
        display = payload.get("display")
        if isinstance(display, str) and display.strip():
            return display.strip()
        for key in (
            "function_response",
            "functionResponse",
            "response",
            "result",
            "data",
            "payload",
            "content",
            "parts",
            "events",
            "candidates",
        ):
            nested = payload.get(key)
            nested_display = _extract_display_from_payload(nested, depth + 1)
            if nested_display:
                return nested_display
        for value in payload.values():
            nested_display = _extract_display_from_payload(value, depth + 1)
            if nested_display:
                return nested_display
    if isinstance(payload, list):
        for item in reversed(payload):
            nested_display = _extract_display_from_payload(item, depth + 1)
            if nested_display:
                return nested_display
    if payload is not None and not isinstance(payload, (int, float, bool, bytes)):
        display_html = getattr(payload, "display_html", None)
        if isinstance(display_html, str) and display_html.strip():
            return display_html.strip()
        display = getattr(payload, "display", None)
        if isinstance(display, str) and display.strip():
            return display.strip()
        for attr in (
            "function_response",
            "functionResponse",
            "response",
            "result",
            "data",
            "payload",
            "content",
            "parts",
            "events",
            "candidates",
        ):
            nested = getattr(payload, attr, None)
            nested_display = _extract_display_from_payload(nested, depth + 1)
            if nested_display:
                return nested_display
        payload_dict = getattr(payload, "__dict__", None)
        if isinstance(payload_dict, dict):
            for value in payload_dict.values():
                nested_display = _extract_display_from_payload(value, depth + 1)
                if nested_display:
                    return nested_display
    return ""


def _extract_preferred_tool_display(function_responses: list[object]) -> str:
    for payload in reversed(function_responses):
        display = _extract_display_from_payload(payload)
        if display:
            return display
    return ""


def _resolve_chat_response_text(result: dict[str, object]) -> str:
    preferred_display = _extract_display_from_payload(result)
    if preferred_display:
        return preferred_display

    raw_response = result.get("response")
    if isinstance(raw_response, str):
        normalized = raw_response.strip()
        if not normalized:
            return "Agent returned no response."
        try:
            parsed_payload = json.loads(normalized)
        except ValueError:
            return normalized
        parsed_display = _extract_display_from_payload(parsed_payload)
        if parsed_display:
            return parsed_display
        return normalized

    nested_display = _extract_display_from_payload(raw_response)
    if nested_display:
        return nested_display
    return "Agent returned no response."


def _extract_deployed_agent_error(payload: object) -> str:
    if isinstance(payload, dict):
        direct_error = payload.get("error")
        if isinstance(direct_error, str) and direct_error.strip():
            return direct_error.strip()
    if not isinstance(payload, dict):
        return ""
    content = payload.get("content")
    if not isinstance(content, dict):
        return ""
    parts = content.get("parts")
    if not isinstance(parts, list):
        return ""
    for part in parts:
        if not isinstance(part, dict):
            continue
        function_response = part.get("function_response")
        if not isinstance(function_response, dict):
            continue
        response = function_response.get("response")
        if not isinstance(response, dict):
            continue
        error = response.get("error")
        if isinstance(error, str) and error.strip():
            return error.strip()
    return ""


def _run_deployed_agent_query(
    uid: str,
    message: str,
    agent_id: str,
    resource_name: str,
    bearer_token: str,
    runtime_session_id: str | None = None,
) -> dict[str, object]:
    import vertexai
    from vertexai import agent_engines

    settings = get_settings()
    if not settings.project_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="PROJECT_ID is required to call deployed Agent Engine.",
        )

    location = _resource_location(resource_name)
    vertexai.init(project=settings.project_id, location=location)
    engine = agent_engines.get(resource_name)

    session_id: str | None = runtime_session_id
    if not session_id and hasattr(engine, "create_session"):
        try:
            session = engine.create_session(
                user_id=uid,
                state={SESSION_BEARER_TOKEN_KEY: bearer_token},
            )
            session_id = _extract_session_id(session)
        except TypeError:
            session = engine.create_session(user_id=uid)
            session_id = _extract_session_id(session)

    response_text = ""
    if hasattr(engine, "stream_query"):
        query_kwargs = {
            "user_id": uid,
            "message": message,
            "state_delta": {SESSION_BEARER_TOKEN_KEY: bearer_token},
        }
        if session_id:
            query_kwargs["session_id"] = session_id
        stream = engine.stream_query(**query_kwargs)
        chunks: list[str] = []
        errors: list[str] = []
        preferred_display = ""
        function_responses: list[object] = []
        try:
            for event in stream:
                event_display = _extract_display_from_payload(event)
                if event_display:
                    preferred_display = event_display
                text = _extract_deployed_agent_text(event)
                if text:
                    chunks.append(text)
                function_responses.extend(_collect_deployed_function_responses(event))
                error = _extract_deployed_agent_error(event)
                if error:
                    errors.append(error)
        except Exception as exc:
            errors.append(str(exc))
        response_text = "\n".join(chunks).strip()
        if not preferred_display:
            preferred_display = _extract_preferred_tool_display(function_responses)
        if preferred_display:
            response_text = preferred_display
        elif not response_text and function_responses:
            payload = function_responses[-1] if len(function_responses) == 1 else function_responses
            response_text = json.dumps(payload, ensure_ascii=False)
        if not response_text and errors:
            response_text = errors[-1]
    elif hasattr(engine, "query"):
        query_kwargs: dict[str, object] = {
            "user_id": uid,
            "message": message,
            "state_delta": {SESSION_BEARER_TOKEN_KEY: bearer_token},
        }
        if session_id:
            query_kwargs["session_id"] = session_id
        result = engine.query(**query_kwargs)
        preferred_display = _extract_display_from_payload(result)
        if preferred_display:
            response_text = preferred_display
        else:
            response_text = _extract_deployed_agent_text(result)
        if not response_text:
            function_response = _extract_deployed_function_response(result)
            if function_response is not None:
                response_text = json.dumps(function_response, ensure_ascii=False)
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Deployed Agent Engine does not expose query/stream_query operations.",
        )

    response_text = response_text or "Agent returned no response."
    return {
        "agent_id": agent_id,
        "message": message,
        "response": response_text,
        "runtime_session_id": session_id,
    }


def _get_owned_chat_session(repository: AgentChatRepository, chat_id: str, user_id: str) -> dict:
    session = repository.get(chat_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found.")
    if session.get("user_id") != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found.")
    return session


def _resolve_chat_session_title(
    user: AuthenticatedUser,
    management_service: AgentManagementService,
    agent_id: str,
    explicit_title: str | None,
) -> str:
    trimmed_title = (explicit_title or "").strip()
    if trimmed_title:
        return trimmed_title
    if agent_id == core.AGENT_GEMINI:
        return "Gemini chat"
    if agent_id == core.AGENT_GPT:
        return "GPT chat"
    if agent_id == core.AGENT_ARTICLE:
        return "Article Agent chat"
    if agent_id == core.AGENT_USERS:
        return "Users Expert Agent chat"
    dynamic_agent = management_service.get_agent(user, agent_id)
    return f"{dynamic_agent.name} chat"


def _build_chat_session_response(session: dict) -> AgentChatSessionResponse:
    messages = session.get("messages")
    message_list = messages if isinstance(messages, list) else []
    last_message_preview = None
    if message_list:
        last_text = message_list[-1].get("text") if isinstance(message_list[-1], dict) else None
        if isinstance(last_text, str):
            last_message_preview = last_text[:80]
    return AgentChatSessionResponse(
        id=session["id"],
        user_id=session["user_id"],
        agent_id=session["agent_id"],
        title=session.get("title") or "Agent chat",
        created_at=session["created_at"],
        updated_at=session["updated_at"],
        message_count=len(message_list),
        last_message_preview=last_message_preview,
    )


def _build_chat_session_detail_response(session: dict) -> AgentChatSessionDetailResponse:
    messages = session.get("messages")
    message_list = messages if isinstance(messages, list) else []
    mapped_messages: list[AgentChatMessage] = []
    for item in message_list:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        text = item.get("text")
        agent_id = item.get("agent_id")
        created_at = item.get("created_at")
        if role not in {ChatMessageRole.USER.value, ChatMessageRole.ASSISTANT.value}:
            continue
        if not isinstance(text, str) or not text.strip():
            continue
        if not isinstance(agent_id, str) or not agent_id.strip():
            continue
        if not isinstance(created_at, datetime):
            continue
        mapped_messages.append(
            AgentChatMessage(
                role=ChatMessageRole(role),
                text=text,
                agent_id=agent_id,
                created_at=created_at,
            )
        )
    summary = _build_chat_session_response(session)
    return AgentChatSessionDetailResponse(
        id=summary.id,
        user_id=summary.user_id,
        agent_id=summary.agent_id,
        title=summary.title,
        created_at=summary.created_at,
        updated_at=summary.updated_at,
        message_count=summary.message_count,
        last_message_preview=summary.last_message_preview,
        messages=mapped_messages,
    )


def _sync_chat_runtime_session(
    chat_repository: AgentChatRepository,
    chat_id: str,
    runtime_session_id: object | None,
) -> None:
    if not isinstance(runtime_session_id, str) or not runtime_session_id.strip():
        return
    chat_repository.update(chat_id=chat_id, values={"runtime_session_id": runtime_session_id.strip()})


def _parse_chat_payload(payload: AgentChatRequest | str) -> AgentChatRequest:
    normalized = normalize_json_payload(payload)
    try:
        return AgentChatRequest.model_validate(normalized)
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.errors()) from exc


def _parse_create_chat_session_payload(
    payload: AgentChatSessionCreateRequest | str,
) -> AgentChatSessionCreateRequest:
    normalized = normalize_json_payload(payload)
    try:
        return AgentChatSessionCreateRequest.model_validate(normalized)
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.errors()) from exc


def _with_auth_debug(
    payload: dict[str, object],
    parsed_payload: AgentChatRequest,
    bearer_token: str,
) -> dict[str, object]:
    result: dict[str, object] = dict(payload)
    if resolve_log_level() != logging.DEBUG:
        return result

    result["request_echo"] = {
        "agent_id": parsed_payload.agent_id,
        "message": parsed_payload.message,
        "model": parsed_payload.model,
    }
    result["auth_debug"] = {
        "token_present": bool(bearer_token),
        "token_length": len(bearer_token or ""),
        "token_preview": (
            f"{bearer_token[:12]}...{bearer_token[-8:]}" if bearer_token and len(bearer_token) > 20 else "<redacted>"
        ),
    }
    return result


@router.get(
    "/agents/available",
    response_class=JSONResponse,
    tags=["Agents"],
    summary="List chat-available agents",
    description="Return legacy static agents plus user's READY deployed agents.",
)
def list_available_agents(
    user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)],
    management_service: Annotated[AgentManagementService, Depends(core.get_management_service)],
) -> JSONResponse:
    settings = get_settings()
    openai_enabled = bool((settings.openai_api_key or "").strip())
    legacy_options = [
        option
        for option in core.LEGACY_AGENT_OPTIONS
        if option.get("id") != core.AGENT_GPT or openai_enabled
    ]
    dynamic_options = []
    for item in management_service.list_agents(user):
        status_value = (
            item.get("status")
            if isinstance(item, dict)
            else getattr(getattr(item, "status", None), "value", getattr(item, "status", None))
        )
        if status_value != "READY":
            continue
        resource_name = (
            item.get("agent_runtime_resource_name")
            if isinstance(item, dict)
            else getattr(item, "agent_runtime_resource_name", None)
        )
        if not resource_name:
            continue
        dynamic_options.append(
            {
                "id": item.get("id") if isinstance(item, dict) else item.id,
                "name": item.get("name") if isinstance(item, dict) else item.name,
                "description": item.get("description") if isinstance(item, dict) else item.description,
            }
        )
    return JSONResponse(
        status_code=200,
        content={"agents": legacy_options + dynamic_options},
    )


@router.get(
    "/agents/chat/sessions",
    response_model=list[AgentChatSessionResponse],
    tags=["Agents"],
    summary="List persisted chat sessions for current user",
)
def list_agent_chat_sessions(
    user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)],
    repository: Annotated[AgentChatRepository, Depends(core.get_chat_repository)],
) -> list[AgentChatSessionResponse]:
    sessions = repository.list_for_user(user.uid)
    return [_build_chat_session_response(item) for item in sessions]


@router.post(
    "/agents/chat/sessions",
    response_model=AgentChatSessionResponse,
    tags=["Agents"],
    summary="Create a persisted chat session",
)
def create_agent_chat_session(
    payload: Annotated[dict | str, Body(description="Create persisted chat session payload.")],
    user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)],
    repository: Annotated[AgentChatRepository, Depends(core.get_chat_repository)],
    management_service: Annotated[AgentManagementService, Depends(core.get_management_service)],
) -> AgentChatSessionResponse:
    parsed_payload = _parse_create_chat_session_payload(payload)
    title = _resolve_chat_session_title(
        user=user,
        management_service=management_service,
        agent_id=parsed_payload.agent_id,
        explicit_title=parsed_payload.title,
    )
    created = repository.create(user_id=user.uid, agent_id=parsed_payload.agent_id, title=title)
    return _build_chat_session_response(created)


@router.get(
    "/agents/chat/sessions/{chat_id}",
    response_model=AgentChatSessionDetailResponse,
    tags=["Agents"],
    summary="Get one persisted chat session",
)
def get_agent_chat_session(
    chat_id: str,
    user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)],
    repository: Annotated[AgentChatRepository, Depends(core.get_chat_repository)],
) -> AgentChatSessionDetailResponse:
    session = _get_owned_chat_session(repository=repository, chat_id=chat_id, user_id=user.uid)
    return _build_chat_session_detail_response(session)


@router.delete(
    "/agents/chat/sessions/{chat_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Agents"],
    summary="Delete one persisted chat session",
)
def delete_agent_chat_session(
    chat_id: str,
    user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)],
    repository: Annotated[AgentChatRepository, Depends(core.get_chat_repository)],
) -> Response:
    _get_owned_chat_session(repository=repository, chat_id=chat_id, user_id=user.uid)
    deleted = repository.delete(chat_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/agents/chat",
    response_class=JSONResponse,
    tags=["Agents"],
    summary="Chat with a selected agent",
)
def chat_with_agent(
    payload: Annotated[dict | str, Body(description="Agent chat payload.")],
    user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)],
    service: Annotated[AgentsService, Depends(core.get_agents_service)],
    management_service: Annotated[AgentManagementService, Depends(core.get_management_service)],
    chat_repository: Annotated[AgentChatRepository, Depends(core.get_chat_repository)],
) -> JSONResponse:
    parsed_payload = _parse_chat_payload(payload)
    requested_agent_id = parsed_payload.agent_id.strip()
    message = parsed_payload.message.strip()
    session_id = parsed_payload.session_id.strip() if parsed_payload.session_id else None

    chat_session = (
        _get_owned_chat_session(repository=chat_repository, chat_id=session_id, user_id=user.uid)
        if session_id
        else None
    )
    agent_id = (chat_session.get("agent_id") if chat_session else requested_agent_id) or requested_agent_id
    if requested_agent_id and requested_agent_id != agent_id:
        agent_id = requested_agent_id

    if chat_session is None:
        title = _resolve_chat_session_title(
            user=user,
            management_service=management_service,
            agent_id=agent_id,
            explicit_title=None,
        )
        chat_session = chat_repository.create(user_id=user.uid, agent_id=agent_id, title=title)
    elif chat_session.get("agent_id") != agent_id:
        title = _resolve_chat_session_title(
            user=user,
            management_service=management_service,
            agent_id=agent_id,
            explicit_title=chat_session.get("title"),
        )
        updated_session = chat_repository.update_session_agent(
            chat_id=chat_session["id"],
            agent_id=agent_id,
            title=title,
        )
        chat_session = updated_session or chat_session

    user_entry = {
        "role": ChatMessageRole.USER.value,
        "text": message,
        "agent_id": agent_id,
        "created_at": datetime.now(timezone.utc),
    }

    if agent_id == core.AGENT_GEMINI:
        model = parsed_payload.model.strip() if parsed_payload.model else "gemini-2.5-flash"
        result = _run_gemini_query(user.uid, prompt=message, model=model)
    elif agent_id == core.AGENT_GPT:
        model = parsed_payload.model.strip() if parsed_payload.model else "gpt-5"
        result = _run_gpt_query(user.uid, prompt=message, model=model, agent_id=core.AGENT_GPT)
    elif agent_id == core.AGENT_ARTICLE:
        remote_resource = _get_remote_agent_resource_name(agent_id)
        result = (
            _run_deployed_agent_query(
                uid=user.uid,
                message=message,
                agent_id=agent_id,
                resource_name=remote_resource,
                bearer_token=service.bearer_token,
                runtime_session_id=chat_session.get("runtime_session_id"),
            )
            if remote_resource
            else _run_article_agent_query(user.uid, message=message, service=service)
        )
    elif agent_id == core.AGENT_USERS:
        remote_resource = _get_remote_agent_resource_name(agent_id)
        result = (
            _run_deployed_agent_query(
                uid=user.uid,
                message=message,
                agent_id=agent_id,
                resource_name=remote_resource,
                bearer_token=service.bearer_token,
                runtime_session_id=chat_session.get("runtime_session_id"),
            )
            if remote_resource
            else _run_users_agent_query(user.uid, message=message, service=service)
        )
    else:
        dynamic_agent = management_service.get_agent(user, agent_id)
        if dynamic_agent.status.value != "READY" or not dynamic_agent.agent_runtime_resource_name:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Agent is not deployed yet. Deploy the agent before chatting.",
            )
        result = _run_deployed_agent_query(
            uid=user.uid,
            message=message,
            agent_id=dynamic_agent.id,
            resource_name=dynamic_agent.agent_runtime_resource_name,
            bearer_token=service.bearer_token,
            runtime_session_id=chat_session.get("runtime_session_id"),
        )

    result["response"] = _resolve_chat_response_text(result)

    _sync_chat_runtime_session(
        chat_repository=chat_repository,
        chat_id=chat_session["id"],
        runtime_session_id=result.get("runtime_session_id"),
    )
    saved = chat_repository.append_messages(
        chat_id=chat_session["id"],
        messages=[
            user_entry,
            {
                "role": ChatMessageRole.ASSISTANT.value,
                "text": result.get("response") or "Agent returned no response.",
                "agent_id": agent_id,
                "created_at": datetime.now(timezone.utc),
            },
        ],
    )
    payload_with_session = {
        **result,
        "session_id": chat_session["id"],
        "chat_session": _build_chat_session_response(saved or chat_session).model_dump(mode="json"),
    }
    return JSONResponse(
        status_code=200,
        content=_with_auth_debug(
            payload=payload_with_session,
            parsed_payload=parsed_payload,
            bearer_token=service.bearer_token,
        ),
    )
