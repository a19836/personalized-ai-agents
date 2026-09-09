from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AgentStatus(str, Enum):
    DRAFT = "DRAFT"
    DEPLOYING = "DEPLOYING"
    READY = "READY"
    FAILED = "FAILED"
    UNDEPLOYING = "UNDEPLOYING"
    UNDEPLOYED = "UNDEPLOYED"


class AgentDefinitionBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=1000)
    model: str = Field(min_length=1, max_length=200)
    instruction: str = Field(min_length=1)
    tools: list[str] = Field(default_factory=list)
    config: dict[str, Any] = Field(
        default_factory=dict,
        description="Extensible additional configuration reserved for future capabilities.",
    )

    @model_validator(mode="after")
    def _validate_tools(self) -> "AgentDefinitionBase":
        if not self.tools:
            raise ValueError("At least one tool must be provided")
        normalized = [item.strip() for item in self.tools if item and item.strip()]
        if not normalized:
            raise ValueError("At least one valid tool must be provided")
        self.tools = normalized
        return self


class AgentCreateRequest(AgentDefinitionBase):
    pass


class AgentUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, min_length=1, max_length=1000)
    model: str | None = Field(default=None, min_length=1, max_length=200)
    instruction: str | None = Field(default=None, min_length=1)
    tools: list[str] | None = None
    config: dict[str, Any] | None = None

    @model_validator(mode="after")
    def _validate_tools(self) -> "AgentUpdateRequest":
        if self.tools is None:
            return self
        normalized = [item.strip() for item in self.tools if item and item.strip()]
        if not normalized:
            raise ValueError("At least one valid tool must be provided")
        self.tools = normalized
        return self


class AgentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    name: str
    description: str
    model: str
    instruction: str
    tools: list[str]
    config: dict[str, Any]
    status: AgentStatus
    agent_runtime_resource_name: str | None = None
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime


class AgentTaskAction(str, Enum):
    DEPLOY = "DEPLOY"
    UNDEPLOY = "UNDEPLOY"


class AgentTaskPayload(BaseModel):
    action: AgentTaskAction
    agent_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
