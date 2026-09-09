from __future__ import annotations

from typing import Callable

from shared.logging import get_logger

from ...service import AgentsService
from .executor import run_research
from ..shared import service_from_context

logger = get_logger(__name__)


def run_web_research(
    user_request: str,
    desired_count: int = 30,
    max_results: int = 20,
    max_pages: int = 20,
    max_subpage_depth: int = 1,
    agent_model: str | None = None,
) -> dict:
    logger.info(
        "web_research request received model=%s desired_count=%s max_results=%s max_pages=%s max_subpage_depth=%s",
        (agent_model or "gemini-2.5-flash").strip(),
        desired_count,
        max_results,
        max_pages,
        max_subpage_depth,
    )
    result = run_research(
        user_request=user_request,
        desired_count=desired_count,
        max_results=max_results,
        max_pages=max_pages,
        max_subpage_depth=max_subpage_depth,
        agent_model=agent_model,
    )
    logger.info(
        "web_research request completed returned_items=%s source_count=%s has_error=%s",
        result.get("returned_items"),
        len(result.get("sources") or []),
        "error" in result,
    )
    return result


def build_web_research_tool(service: AgentsService, agent_model: str | None = None) -> Callable:
    def web_research(
        user_request: str,
        tool_context,
        desired_count: int = 30,
        max_results: int = 20,
        max_pages: int = 20,
        max_subpage_depth: int = 1,
    ) -> dict:
        """
        Run generic web research for a user request and return structured findings.

        Supports two modes automatically:
        1. Direct URL extraction when the request includes specific URLs and asks for data from them.
        2. Search-driven research when URLs are not provided or additional coverage is needed.

        The workflow can discover subpages and extract objective-specific fields from page content.
        """
        logger.debug(
            "web_research tool invoked desired_count=%s max_results=%s max_pages=%s max_subpage_depth=%s",
            desired_count,
            max_results,
            max_pages,
            max_subpage_depth,
        )
        scoped = service_from_context(service, tool_context)
        return scoped.web_research(
            user_request=user_request,
            desired_count=desired_count,
            max_results=max_results,
            max_pages=max_pages,
            max_subpage_depth=max_subpage_depth,
            agent_model=agent_model,
        )

    return web_research
