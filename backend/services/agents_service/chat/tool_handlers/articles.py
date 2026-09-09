from __future__ import annotations

from typing import Callable

from ..service import AgentsService
from .shared import service_from_context


def build_list_articles_tool(service: AgentsService) -> Callable:
    def list_articles(tool_context) -> list[dict]:
        scoped = service_from_context(service, tool_context)
        return scoped.list_articles()

    return list_articles


def build_get_article_tool(service: AgentsService) -> Callable:
    def get_article(article_id: str, tool_context) -> dict:
        scoped = service_from_context(service, tool_context)
        return scoped.get_article(article_id)

    return get_article
