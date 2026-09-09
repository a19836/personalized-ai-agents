from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Header, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from shared.auth import AuthenticatedUser
from shared.config import get_settings
from shared.fastapi import get_authenticated_user
from shared.http import normalize_json_payload

from services.agents_service.admin.service import AgentManagementService
from services.agents_service.admin.models import AgentCreateRequest, AgentResponse, AgentTaskPayload, AgentUpdateRequest
from services.agents_service import main as core

router = APIRouter()

InternalTaskSecretHeader = Annotated[str | None, Header(alias="X-Agents-Task-Secret")]


def _parse_create_agent_payload(payload: AgentCreateRequest | str) -> AgentCreateRequest:
    normalized = normalize_json_payload(payload)
    try:
        return AgentCreateRequest.model_validate(normalized)
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.errors()) from exc


def _parse_update_agent_payload(payload: AgentUpdateRequest | str) -> AgentUpdateRequest:
    normalized = normalize_json_payload(payload)
    try:
        return AgentUpdateRequest.model_validate(normalized)
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.errors()) from exc


def _parse_task_payload(payload: AgentTaskPayload | str) -> AgentTaskPayload:
    normalized = normalize_json_payload(payload)
    try:
        return AgentTaskPayload.model_validate(normalized)
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.errors()) from exc


@router.get(
    "/agents",
    response_model=list[AgentResponse],
    tags=["Agents"],
    summary="List current user's agents",
)
def list_agents(
    user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)],
    service: Annotated[AgentManagementService, Depends(core.get_management_service)],
) -> list[AgentResponse]:
    return service.list_agents(user)


@router.post(
    "/agents",
    response_model=AgentResponse,
    tags=["Agents"],
    summary="Create a new agent",
)
def create_agent(
    payload: Annotated[dict | str, Body(description="Agent definition payload.")],
    user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)],
    service: Annotated[AgentManagementService, Depends(core.get_management_service)],
) -> AgentResponse:
    parsed_payload = _parse_create_agent_payload(payload)
    return service.create_agent(user, parsed_payload)


@router.get(
    "/agents/{agent_id}",
    response_model=AgentResponse,
    tags=["Agents"],
    summary="Get one agent",
)
def get_agent(
    agent_id: str,
    user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)],
    service: Annotated[AgentManagementService, Depends(core.get_management_service)],
) -> AgentResponse:
    return service.get_agent(user, agent_id)


@router.put(
    "/agents/{agent_id}",
    response_model=AgentResponse,
    tags=["Agents"],
    summary="Update one agent",
)
def update_agent(
    agent_id: str,
    payload: Annotated[dict | str, Body(description="Agent definition update payload.")],
    user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)],
    service: Annotated[AgentManagementService, Depends(core.get_management_service)],
) -> AgentResponse:
    parsed_payload = _parse_update_agent_payload(payload)
    return service.update_agent(user, agent_id, parsed_payload)


@router.post(
    "/agents/{agent_id}/deploy",
    response_class=JSONResponse,
    tags=["Agents"],
    summary="Start async deployment",
)
def deploy_agent(
    agent_id: str,
    user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)],
    service: Annotated[AgentManagementService, Depends(core.get_management_service)],
) -> JSONResponse:
    service.request_deploy(user, agent_id)
    return JSONResponse(status_code=status.HTTP_202_ACCEPTED, content={"status": "DEPLOYING"})


@router.delete(
    "/agents/{agent_id}",
    response_class=JSONResponse,
    tags=["Agents"],
    summary="Start async undeploy and delete",
)
def delete_agent(
    agent_id: str,
    user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)],
    service: Annotated[AgentManagementService, Depends(core.get_management_service)],
) -> JSONResponse:
    service.request_delete(user, agent_id)
    return JSONResponse(status_code=status.HTTP_202_ACCEPTED, content={"status": "UNDEPLOYING"})


@router.post(
    "/internal/agents/tasks/process",
    response_class=JSONResponse,
    include_in_schema=False,
)
def process_agent_task(
    payload: Annotated[dict | str, Body(description="Internal task payload.")],
    task_secret: InternalTaskSecretHeader = None,
    service: AgentManagementService = Depends(core.get_management_service),
) -> JSONResponse:
    expected = (get_settings().agent_tasks_secret or "").strip()
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AGENT_TASKS_SECRET is not configured.",
        )
    if (task_secret or "").strip() != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized internal task call.")
    parsed_payload = _parse_task_payload(payload)
    service.process_task(parsed_payload)
    return JSONResponse(status_code=status.HTTP_200_OK, content={"status": "OK"})
