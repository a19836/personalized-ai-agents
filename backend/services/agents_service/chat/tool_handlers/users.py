from __future__ import annotations

from typing import Callable

from ..service import AgentsService
from .shared import service_from_context


def build_get_my_profile_tool(service: AgentsService) -> Callable:
    def get_my_profile(tool_context) -> dict:
        scoped = service_from_context(service, tool_context)
        return scoped.get_current_user_profile()

    return get_my_profile


def build_update_my_profile_tool(service: AgentsService) -> Callable:
    def update_my_profile(
        tool_context,
        display_name: str | None = None,
        role: str | None = None,
    ) -> dict:
        scoped = service_from_context(service, tool_context)
        return scoped.update_current_user_profile(display_name=display_name, role=role)

    return update_my_profile
