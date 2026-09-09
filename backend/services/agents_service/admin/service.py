from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, status

from services.agents_service.admin.agent_deployer import AgentDeployer
from services.agents_service.admin.agent_factory import normalize_tools
from services.agents_service.admin.models import (
    AgentCreateRequest,
    AgentResponse,
    AgentStatus,
    AgentTaskAction,
    AgentTaskPayload,
    AgentUpdateRequest,
)
from services.agents_service.admin.repository import AgentRepository
from services.agents_service.admin.task_scheduler import AgentTaskScheduler
from shared.auth import AuthenticatedUser
from shared.logging import get_logger

logger = get_logger(__name__)


@dataclass
class AgentManagementService:
    repository: AgentRepository
    deployer: AgentDeployer
    scheduler: AgentTaskScheduler

    def list_agents(self, user: AuthenticatedUser) -> list[AgentResponse]:
        return [AgentResponse.model_validate(item) for item in self.repository.list_for_user(user.uid)]

    def create_agent(self, user: AuthenticatedUser, payload: AgentCreateRequest) -> AgentResponse:
        normalized_tools = normalize_tools(payload.tools)
        created = self.repository.create(
            user.uid,
            {
                "name": payload.name.strip(),
                "description": payload.description.strip(),
                "model": payload.model.strip(),
                "instruction": payload.instruction.strip(),
                "tools": normalized_tools,
                "config": payload.config or {},
            },
        )
        return AgentResponse.model_validate(created)

    def get_agent(self, user: AuthenticatedUser, agent_id: str) -> AgentResponse:
        agent = self._get_owned_agent(user, agent_id)
        return AgentResponse.model_validate(agent)

    def update_agent(self, user: AuthenticatedUser, agent_id: str, payload: AgentUpdateRequest) -> AgentResponse:
        current = self._get_owned_agent(user, agent_id)
        if current["status"] in {AgentStatus.DEPLOYING.value, AgentStatus.UNDEPLOYING.value}:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Agent cannot be updated while deployment operation is in progress.",
            )

        updates = payload.model_dump(exclude_unset=True)
        if "tools" in updates:
            updates["tools"] = normalize_tools(updates["tools"])
        if "config" in updates and updates["config"] is None:
            updates["config"] = {}
        for field_name in ("name", "description", "model", "instruction"):
            if field_name in updates and isinstance(updates[field_name], str):
                updates[field_name] = updates[field_name].strip()

        if self._is_deployable_config_changed(current, updates):
            updates["status"] = AgentStatus.DRAFT.value
            updates["last_error"] = None

        saved = self.repository.update(agent_id, updates)
        if not saved:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
        return AgentResponse.model_validate(saved)

    def request_deploy(self, user: AuthenticatedUser, agent_id: str) -> None:
        agent = self._get_owned_agent(user, agent_id)
        if agent["status"] in {AgentStatus.DEPLOYING.value, AgentStatus.UNDEPLOYING.value}:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Agent deployment already in progress.")

        self.repository.update(
            agent_id,
            {
                "status": AgentStatus.DEPLOYING.value,
                "last_error": None,
            },
        )
        self.scheduler.schedule(
            AgentTaskPayload(action=AgentTaskAction.DEPLOY, agent_id=agent_id, user_id=user.uid)
        )

    def request_delete(self, user: AuthenticatedUser, agent_id: str) -> None:
        agent = self._get_owned_agent(user, agent_id)
        if agent["status"] in {AgentStatus.DEPLOYING.value, AgentStatus.UNDEPLOYING.value}:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Agent cannot be deleted while deployment operation is in progress.",
            )

        self.repository.update(agent_id, {"status": AgentStatus.UNDEPLOYING.value, "last_error": None})
        self.scheduler.schedule(
            AgentTaskPayload(action=AgentTaskAction.UNDEPLOY, agent_id=agent_id, user_id=user.uid)
        )

    def process_task(self, payload: AgentTaskPayload) -> None:
        agent = self.repository.get(payload.agent_id)
        if not agent:
            logger.warning("Agent task ignored because agent does not exist agent_id=%s", payload.agent_id)
            return
        if agent["user_id"] != payload.user_id:
            logger.warning(
                "Agent task ownership mismatch agent_id=%s payload_uid=%s doc_uid=%s",
                payload.agent_id,
                payload.user_id,
                agent["user_id"],
            )
            return

        if payload.action == AgentTaskAction.DEPLOY:
            self._process_deploy(agent)
            return
        self._process_undeploy(agent)

    def _process_deploy(self, agent: dict[str, Any]) -> None:
        agent_id = agent["id"]
        previous_runtime = (agent.get("agent_runtime_resource_name") or "").strip()
        try:
            if previous_runtime:
                self.deployer.undeploy(previous_runtime)
            resource_name = self.deployer.deploy(agent)
            self.repository.update(
                agent_id,
                {
                    "status": AgentStatus.READY.value,
                    "agent_runtime_resource_name": resource_name,
                    "last_error": None,
                },
            )
        except Exception as exc:
            self.repository.update(
                agent_id,
                {
                    "status": AgentStatus.FAILED.value,
                    "last_error": str(exc),
                },
            )
            logger.exception("Agent deployment failed agent_id=%s", agent_id)

    def _process_undeploy(self, agent: dict[str, Any]) -> None:
        agent_id = agent["id"]
        runtime_resource = (agent.get("agent_runtime_resource_name") or "").strip()
        try:
            if runtime_resource:
                self.deployer.undeploy(runtime_resource)
            self.repository.delete(agent_id)
        except Exception as exc:
            self.repository.update(
                agent_id,
                {
                    "status": AgentStatus.FAILED.value,
                    "last_error": str(exc),
                },
            )
            logger.exception("Agent undeploy failed agent_id=%s", agent_id)

    @staticmethod
    def _is_deployable_config_changed(current: dict[str, Any], updates: dict[str, Any]) -> bool:
        for key in ("name", "description", "model", "instruction", "tools", "config"):
            if key not in updates:
                continue
            if current.get(key) != updates[key]:
                return True
        return False

    def _get_owned_agent(self, user: AuthenticatedUser, agent_id: str) -> dict[str, Any]:
        agent = self.repository.get(agent_id)
        if not agent:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
        if agent["user_id"] != user.uid:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
        return agent
