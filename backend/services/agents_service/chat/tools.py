from __future__ import annotations

from typing import Callable

from .service import AgentsService
from .tool_handlers.articles import build_get_article_tool, build_list_articles_tool
from .tool_handlers.fetch_url_content import build_fetch_url_content_tool
from .tool_handlers.users import build_get_my_profile_tool, build_update_my_profile_tool
from .tool_handlers.web_research.research import build_web_research_tool
from .tool_handlers.web_search.search import build_web_search_tool

ToolBuilder = Callable[..., Callable]


def build_tool(name: str, service: AgentsService, agent_model: str | None = None) -> Callable:
    builder = TOOLS[name]
    if name in {"web_search", "web_research"}:
        return builder(service, agent_model)
    return builder(service)


TOOLS: dict[str, ToolBuilder] = {
    "list_articles": build_list_articles_tool,
    "get_article": build_get_article_tool,
    "get_my_profile": build_get_my_profile_tool,
    "update_my_profile": build_update_my_profile_tool,
    "web_search": build_web_search_tool,
    "web_research": build_web_research_tool,
    "fetch_url_content": build_fetch_url_content_tool,
}

TOOL_GROUPS: dict[str, list[str]] = {
    "articles": ["list_articles", "get_article"],
    "users": ["get_my_profile", "update_my_profile"],
    "web": ["web_search"],
    "research": ["web_research"],
}


def normalize_tools(requested_tools: list[str]) -> list[str]:
    expanded: list[str] = []
    for item in requested_tools:
        name = item.strip()
        if not name:
            continue
        if name in TOOL_GROUPS:
            expanded.extend(TOOL_GROUPS[name])
        else:
            expanded.append(name)

    deduped: list[str] = []
    seen: set[str] = set()
    for name in expanded:
        if name in seen:
            continue
        seen.add(name)
        deduped.append(name)

    unsupported = [name for name in deduped if name not in TOOLS]
    if unsupported:
        allowed = sorted(list(TOOLS.keys()) + list(TOOL_GROUPS.keys()))
        raise ValueError(f"Unsupported tools: {unsupported}. Allowed tools: {allowed}")
    return deduped
