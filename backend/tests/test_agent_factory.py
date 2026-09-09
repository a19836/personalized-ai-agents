from __future__ import annotations

import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.agents_service.admin.agent_factory import (  # noqa: E402
    _instruction_suffix_for_tools,
    create_agent,
    normalize_tools,
)
from services.agents_service.chat.service import AgentsService  # noqa: E402


class AgentFactoryTest(unittest.TestCase):
    def test_normalize_tools_expands_groups(self) -> None:
        self.assertEqual(
            normalize_tools(["articles", "users", "web"]),
            ["list_articles", "get_article", "get_my_profile", "update_my_profile", "web_search"],
        )

    def test_normalize_tools_rejects_unsupported(self) -> None:
        with self.assertRaises(ValueError):
            normalize_tools(["unknown_tool"])

    def test_normalize_tools_supports_fetch_url_content(self) -> None:
        self.assertEqual(normalize_tools(["fetch_url_content"]), ["fetch_url_content"])

    def test_create_agent_builds_dynamic_agent(self) -> None:
        try:
            import google.adk.agents  # noqa: F401
        except ModuleNotFoundError:
            self.skipTest("google.adk is not installed in this environment")

        agent = create_agent(
            {
                "id": "agent-1",
                "name": "Articles Assistant",
                "description": "Helps with articles",
                "model": "gemini-2.5-flash",
                "instruction": "Summarize my articles",
                "tools": ["list_articles", "get_article"],
            },
            AgentsService(bearer_token=""),
        )
        self.assertEqual(agent.name, "articles_assistant")
        self.assertEqual(agent.model, "gemini-2.5-flash")
        self.assertEqual(len(agent.tools), 2)

    def test_instruction_suffix_applied_only_for_web_tools(self) -> None:
        no_suffix = _instruction_suffix_for_tools(["list_articles"])
        with_suffix = _instruction_suffix_for_tools(["web_research"])
        self.assertEqual(no_suffix, "")
        self.assertIn("Do not say you are still working", with_suffix)


if __name__ == "__main__":
    unittest.main()
