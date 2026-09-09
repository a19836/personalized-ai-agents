from __future__ import annotations

import re
from typing import Any

from services.agents_service.chat.service import AgentsService
from services.agents_service.chat.tools import build_tool, normalize_tools


def _sanitize_agent_name(name: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_]+", "_", name.strip().lower())
    normalized = normalized.strip("_")
    return normalized or "dynamic_agent"


def _instruction_suffix_for_tools(tool_names: list[str]) -> str:
    if not any(name in {"web_search", "web_research", "fetch_url_content"} for name in tool_names):
        return ""
    return (
        "\n\n"
        "Critical response rules for web research tools:\n"
        "- Do not say you are still working, processing, or that the user should wait.\n"
        "- Do not promise future follow-up messages.\n"
        "- Do not claim you cannot fetch, inspect, or extract from provided public URLs.\n"
        "- If the user provides URL(s) and asks for extraction from them, call web_research and return results.\n"
        "- When web_search or web_research is needed, call the tool and return one final response in the same turn.\n"
        "- If the tool fails, return the failure clearly instead of pretending work continues."
    )


def create_agent(agent_definition: dict, service: AgentsService) -> Any:
    from google.adk.agents import Agent

    tool_names = normalize_tools(agent_definition.get("tools") or [])
    agent_model = str(agent_definition.get("model") or "").strip() or None
    tools = [build_tool(name, service, agent_model=agent_model) for name in tool_names]
    base_instruction = str(agent_definition.get("instruction") or "").strip()
    instruction = f"{base_instruction}{_instruction_suffix_for_tools(tool_names)}"
    return Agent(
        name=_sanitize_agent_name(agent_definition["name"]),
        model=agent_definition["model"],
        description=agent_definition["description"],
        instruction=instruction,
        tools=tools,
    )
