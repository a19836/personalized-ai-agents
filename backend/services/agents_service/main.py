from __future__ import annotations

import functions_framework
from fastapi import FastAPI, HTTPException, Response, status
from flask import Request, Response as FlaskResponse
from shared.auth import extract_bearer_token
from shared.config import get_settings
from shared.fastapi import (
    AuthorizationHeader,
    add_cors_middleware,
    get_authenticated_user,
    run_fastapi_as_cloud_function,
)
from shared.logging import configure_logging, get_logger

from google import genai
from google.genai.types import HttpOptions
from services.agents_service.admin.agent_deployer import AgentDeployer
from services.agents_service.admin.service import AgentManagementService
from services.agents_service.admin.models import AgentTaskPayload
from services.agents_service.admin.repository import AgentRepository
from services.agents_service.chat.repository import AgentChatRepository
from services.agents_service.admin.task_scheduler import AgentTaskScheduler
from services.agents_service.chat.service import AgentsService

configure_logging()
logger = get_logger(__name__)

AGENT_GEMINI = "gemini"
AGENT_GPT = "gpt"
AGENT_ARTICLE = "article_agent"
AGENT_USERS = "users_expert_agent"
LEGACY_AGENT_OPTIONS = [
    {
        "id": AGENT_GEMINI,
        "name": "Gemini Assistant - Default",
        "description": "General purpose Gemini chat.",
    },
    {
        "id": AGENT_GPT,
        "name": "GPT Assistant - Default",
        "description": "General purpose GPT chat.",
    },
    {
        "id": AGENT_ARTICLE,
        "name": "Article Agent - Default",
        "description": "Uses tools to list and read your articles.",
    },
    {
        "id": AGENT_USERS,
        "name": "Users Expert Agent - Default",
        "description": "Specialized in reading and updating the current user profile.",
    },
]

app = FastAPI(
    title="Agents Service",
    summary="Create, deploy, and interact with user-managed AI agents.",
    description=(
        "Typed API for user-scoped agent CRUD and deployment lifecycle. "
        "Protected endpoints require a Firebase bearer token."
    ),
    version="1.0.0",
)
add_cors_middleware(app, allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])


def _process_agent_task_local(payload: AgentTaskPayload) -> None:
    management_service = AgentManagementService(
        repository=AgentRepository(),
        deployer=AgentDeployer(),
        scheduler=AgentTaskScheduler(local_handler=_process_agent_task_local),
    )
    management_service.process_task(payload)


def get_management_service() -> AgentManagementService:
    return AgentManagementService(
        repository=AgentRepository(),
        deployer=AgentDeployer(),
        scheduler=AgentTaskScheduler(local_handler=_process_agent_task_local),
    )


def get_agents_service(authorization: AuthorizationHeader = None) -> AgentsService:
    token = extract_bearer_token(authorization)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Bearer token")
    return AgentsService(bearer_token=token)


def get_chat_repository() -> AgentChatRepository:
    return AgentChatRepository()


def get_gemini_client() -> genai.Client:
    settings = get_settings()
    if not settings.project_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="PROJECT_ID is required to call Gemini.",
        )
    return genai.Client(
        enterprise=True,
        project=settings.project_id,
        location="global",
        http_options=HttpOptions(api_version="v1"),
    )


@app.get("/healthz", tags=["System"], summary="Check service health")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.options("/", include_in_schema=False)
@app.options("/{path:path}", include_in_schema=False)
def options_handler(path: str = "") -> Response:
    del path
    return Response(status_code=status.HTTP_204_NO_CONTENT)

from services.agents_service.admin.main import router as admin_router
from services.agents_service.chat.main import router as chat_router

app.include_router(chat_router)
app.include_router(admin_router)


def _run_deployed_agent_query(**kwargs: object) -> dict[str, object]:
    from services.agents_service.chat.main import _run_deployed_agent_query as chat_run_deployed_agent_query

    return chat_run_deployed_agent_query(**kwargs)


@functions_framework.http
def agents_service(request: Request) -> FlaskResponse:
    logger.debug(
        "Agents service request method=%s path=%s",
        request.method.upper(),
        request.path.rstrip("/") or "/",
    )
    return run_fastapi_as_cloud_function(app, request)
