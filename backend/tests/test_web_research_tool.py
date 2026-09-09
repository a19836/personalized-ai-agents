from __future__ import annotations

import unittest
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.agents_service.chat.tool_handlers.fetch_url_content import fetch_url_content
from services.agents_service.chat.tool_handlers.web_research.executor import run_research
from services.agents_service.chat.tool_handlers.web_research.info_extractor import extract_items_from_sources
from services.agents_service.chat.tool_handlers.web_research.models import ExtractedItem, ExtractionField, ResearchPlan
from services.agents_service.chat.tools import normalize_tools


class WebResearchToolTests(unittest.TestCase):
    def test_normalize_tools_supports_research_group(self) -> None:
        normalized = normalize_tools(["research"])
        self.assertEqual(normalized, ["web_research"])

    def test_fetch_url_content_extracts_visible_text(self) -> None:
        response = SimpleNamespace(
            text="<html><head><title>Acme</title></head><body><h1>Hello</h1><script>ignored()</script></body></html>",
            status_code=200,
            headers={"content-type": "text/html; charset=utf-8"},
            url="https://acme.example",
            raise_for_status=lambda: None,
        )
        with patch("services.agents_service.chat.tool_handlers.fetch_url_content.requests.get", return_value=response):
            result = fetch_url_content("https://acme.example")

        self.assertEqual(result["title"], "Acme")
        self.assertIn("Hello", result["text_content"])
        self.assertNotIn("ignored()", result["text_content"])

    def test_fetch_url_content_rejects_private_hosts(self) -> None:
        result = fetch_url_content("http://127.0.0.1/private")
        self.assertIn("error", result)

    def test_run_research_returns_structured_items(self) -> None:
        plan = ResearchPlan(
            objective="Map major space companies",
            search_queries=["major space companies list"],
            extraction_fields=[
                ExtractionField(name="company", description="Company"),
                ExtractionField(name="headquarters", description="Headquarters"),
                ExtractionField(name="website", description="Website"),
            ],
            target_items=2,
            max_results=10,
            max_pages=10,
            require_verification=True,
            additional_research_allowed=False,
        )
        items = [
            ExtractedItem(
                data={
                    "company": "Space Corp",
                    "headquarters": "Lisbon, Portugal",
                    "website": "https://spacecorp.example",
                },
                source_url="https://spacecorp.example/contact",
                confidence="high",
            ),
            ExtractedItem(
                data={
                    "company": "Orbit Labs",
                    "headquarters": "Porto, Portugal",
                    "website": "https://orbitlabs.example",
                },
                source_url="https://orbitlabs.example/contact",
                confidence="medium",
            ),
        ]

        with (
            patch("services.agents_service.chat.tool_handlers.web_research.executor.create_research_plan", return_value=plan),
            patch("services.agents_service.chat.tool_handlers.web_research.executor._build_client", return_value=object()),
            patch("services.agents_service.chat.tool_handlers.web_research.executor.discover_relevant_subpages", return_value=[]) as discover_mock,
            patch(
                "services.agents_service.chat.tool_handlers.web_research.executor.search_web",
                return_value={
                    "query": "major space companies list",
                    "sources": [
                        {"title": "Space Corp", "url": "https://spacecorp.example/contact"},
                        {"title": "Orbit Labs", "url": "https://orbitlabs.example/contact"},
                    ],
                },
            ),
            patch(
                "services.agents_service.chat.tool_handlers.web_research.executor.extract_items_from_sources",
                return_value=items,
            ),
        ):
            result = run_research(user_request="list 2 major space companies", desired_count=2)

        self.assertEqual(result["query"], "list 2 major space companies")
        self.assertEqual(result["requested_items"], 2)
        self.assertEqual(result["returned_items"], 2)
        self.assertEqual(len(result["items"]), 2)
        self.assertEqual(result["items"][0]["data"]["company"], "Space Corp")
        self.assertTrue(result["coverage"]["enough_items"])
        self.assertEqual(discover_mock.call_count, 0)

    def test_run_research_includes_subpages_for_extraction(self) -> None:
        plan = ResearchPlan(
            objective="Collect public API docs details",
            search_queries=["acme api documentation features"],
            extraction_fields=[
                ExtractionField(name="feature", description="Feature name"),
                ExtractionField(name="details", description="Feature details"),
            ],
            target_items=1,
            max_results=10,
            max_pages=10,
            max_subpage_depth=1,
            require_verification=True,
            additional_research_allowed=False,
        )
        items = [
            ExtractedItem(
                data={"feature": "Webhooks", "details": "Supports retries"},
                source_url="https://acme.example/docs/webhooks",
                confidence="high",
            )
        ]

        with (
            patch("services.agents_service.chat.tool_handlers.web_research.executor.create_research_plan", return_value=plan),
            patch("services.agents_service.chat.tool_handlers.web_research.executor._build_client", return_value=object()),
            patch(
                "services.agents_service.chat.tool_handlers.web_research.executor.search_web",
                return_value={"query": "acme api documentation features", "sources": [{"title": "Docs", "url": "https://acme.example/docs"}]},
            ),
            patch(
                "services.agents_service.chat.tool_handlers.web_research.executor.discover_relevant_subpages",
                return_value=["https://acme.example/docs/webhooks"],
            ),
            patch(
                "services.agents_service.chat.tool_handlers.web_research.executor.extract_items_from_sources",
                side_effect=[[], items],
            ) as extract_mock,
        ):
            result = run_research(user_request="find api features", desired_count=1)

        self.assertEqual(extract_mock.call_count, 2)
        first_call_urls = [entry["url"] for entry in extract_mock.call_args_list[0].kwargs["sources"]]
        second_call_urls = [entry["url"] for entry in extract_mock.call_args_list[1].kwargs["sources"]]
        self.assertEqual(first_call_urls, ["https://acme.example/docs"])
        self.assertEqual(second_call_urls, ["https://acme.example/docs/webhooks"])
        self.assertEqual(result["coverage"]["subpage_depth_used"], 1)

    def test_run_research_uses_direct_url_from_request(self) -> None:
        plan = ResearchPlan(
            objective="Extract details from a provided page",
            search_queries=["should not be used when direct URL already satisfies target"],
            extraction_fields=[
                ExtractionField(name="feature", description="Feature name"),
                ExtractionField(name="details", description="Feature details"),
            ],
            target_items=1,
            max_results=10,
            max_pages=10,
            max_subpage_depth=1,
            require_verification=True,
            additional_research_allowed=False,
        )
        items = [
            ExtractedItem(
                data={"feature": "Webhooks", "details": "Supports retries"},
                source_url="https://acme.example/docs",
                confidence="high",
            )
        ]

        with (
            patch("services.agents_service.chat.tool_handlers.web_research.executor.create_research_plan", return_value=plan),
            patch("services.agents_service.chat.tool_handlers.web_research.executor._build_client", return_value=object()),
            patch(
                "services.agents_service.chat.tool_handlers.web_research.executor.extract_items_from_sources",
                return_value=items,
            ) as extract_mock,
            patch("services.agents_service.chat.tool_handlers.web_research.executor.search_web") as search_mock,
        ):
            result = run_research(
                user_request="Extract API details from https://acme.example/docs for me",
                desired_count=1,
            )

        self.assertEqual(extract_mock.call_count, 1)
        direct_urls = [entry["url"] for entry in extract_mock.call_args_list[0].kwargs["sources"]]
        self.assertEqual(direct_urls, ["https://acme.example/docs"])
        search_mock.assert_not_called()
        self.assertEqual(result["returned_items"], 1)
        self.assertEqual(result["sources"][0]["url"], "https://acme.example/docs")

    def test_extract_items_uses_tool_selected_by_gemini(self) -> None:
        extraction_fields = [ExtractionField(name="company", description="Company name")]
        response = SimpleNamespace(text='{"items":[{"company":"Space Corp","confidence":"high"}]}')
        with patch(
            "services.agents_service.chat.tool_handlers.web_research.info_extractor._choose_extraction_tool",
            return_value="url_context",
        ) as choose_mock, patch(
            "services.agents_service.chat.tool_handlers.web_research.info_extractor.generate_content_with_tools",
            return_value=response,
        ) as generate_mock:
            items = extract_items_from_sources(
                client=object(),
                model="gemini-2.5-flash",
                query="Find company",
                sources=[{"title": "Source", "url": "https://spacecorp.example"}],
                extraction_fields=extraction_fields,
            )

        self.assertEqual(len(items), 1)
        self.assertEqual(choose_mock.call_count, 1)
        self.assertEqual(generate_mock.call_count, 1)
        self.assertEqual(generate_mock.call_args.kwargs["tool_names"], ["url_context"])

    def test_extract_items_can_use_fetch_when_gemini_selects_it(self) -> None:
        extraction_fields = [ExtractionField(name="company", description="Company name")]
        response = SimpleNamespace(text='{"items":[{"company":"Space Corp","confidence":"high"}]}')
        with patch(
            "services.agents_service.chat.tool_handlers.web_research.info_extractor._choose_extraction_tool",
            return_value="fetch_url_content",
        ), patch(
            "services.agents_service.chat.tool_handlers.web_research.info_extractor.generate_content_with_tools",
            return_value=response,
        ) as generate_mock:
            items = extract_items_from_sources(
                client=object(),
                model="gemini-2.5-flash",
                query="Find company",
                sources=[{"title": "Source", "url": "https://spacecorp.example"}],
                extraction_fields=extraction_fields,
            )

        self.assertEqual(len(items), 1)
        self.assertEqual(generate_mock.call_count, 1)
        self.assertEqual(generate_mock.call_args.kwargs["tool_names"], ["fetch_url_content"])


if __name__ == "__main__":
    unittest.main()
