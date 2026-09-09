from __future__ import annotations

from google.adk.agents import Agent

from ..chat.service import AgentsService
from ..chat.tools import build_tool
from ..chat.tool_handlers.shared import SESSION_BEARER_TOKEN_KEY


def build_articles_agent(service: AgentsService) -> Agent:
    """Build a root agent whose tools are bound to the given AgentsService instance."""
    get_article = build_tool("get_article", service)
    list_articles = build_tool("list_articles", service)

    return Agent(
        name="article_agent",
        model="gemini-2.5-flash",
        description="An assistant that helps users find and understand articles.",
        instruction="""
        You are an article assistant.

        Help users find and understand articles.

        Use list_articles to show available articles when the user asks what is available.
        Use get_article with the article's ID when the user asks about a specific article.
        """,
        tools=[get_article, list_articles],
    )


def build_users_agent(service: AgentsService) -> Agent:
    """Build an agent specialized in current-user profile operations."""
    get_my_profile = build_tool("get_my_profile", service)
    update_my_profile = build_tool("update_my_profile", service)

    return Agent(
        name="users_expert_agent",
        model="gemini-2.5-flash",
        description="An assistant specialized in user profile questions and updates.",
        instruction="""
        You are a users expert assistant.

        Use get_my_profile whenever the user asks about their account, profile, role, or preferences.
        Use update_my_profile only when the user explicitly asks to change display name or role.
        Keep responses concise and include only relevant user fields.
        """,
        tools=[get_my_profile, update_my_profile],
    )

# Keep compatibility with ADK loader that expects `root_agent`.
root_agent = build_articles_agent(
    AgentsService(bearer_token=""),
)
