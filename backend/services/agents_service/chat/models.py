from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ChatMessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"


class AgentChatSessionCreateRequest(BaseModel):
    agent_id: str = Field(min_length=1)
    title: str | None = Field(default=None, max_length=200)


class AgentChatMessage(BaseModel):
    role: ChatMessageRole
    text: str = Field(min_length=1)
    agent_id: str = Field(min_length=1)
    created_at: datetime


class AgentChatSessionResponse(BaseModel):
    id: str
    user_id: str
    agent_id: str
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0
    last_message_preview: str | None = None


class AgentChatSessionDetailResponse(AgentChatSessionResponse):
    messages: list[AgentChatMessage] = Field(default_factory=list)
