from __future__ import annotations

import unittest
from types import SimpleNamespace
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.agents_service.chat.tool_handlers.web_search.search import format_web_search_response
from services.agents_service.chat.tool_handlers.web_search.search import format_web_search_response_html
from services.agents_service.chat.tool_handlers.shared import generate_content_with_tools
from services.agents_service.chat.tool_handlers.web_search.search import search_web


class _FakeModels:
    def __init__(self, interaction: object, error: Exception | None = None) -> None:
        self._interaction = interaction
        self._error = error
        self.calls = 0

    def generate_content(self, **kwargs):  # noqa: ANN003
        del kwargs
        self.calls += 1
        if self._error:
            raise self._error
        if isinstance(self._interaction, list):
            index = min(self.calls - 1, len(self._interaction) - 1)
            return self._interaction[index]
        return self._interaction


class _FakeClient:
    def __init__(self, interaction: object, error: Exception | None = None) -> None:
        self.models = _FakeModels(interaction, error=error)


class _VariantClient:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

        class _Models:
            def __init__(self, parent: "_VariantClient") -> None:
                self.parent = parent

            def generate_content(self, **kwargs):  # noqa: ANN003
                config = kwargs.get("config")
                tools = getattr(config, "tools", None) or []
                names = [type(tool).__name__ for tool in tools]
                self.parent.calls.append(names)
                if names == ["GoogleSearch", "UrlContext"]:
                    return {"ok": "direct"}
                raise RuntimeError("variant not accepted")

        self.models = _Models(self)


class WebSearchToolTests(unittest.TestCase):
    def test_create_interaction_with_tools_tries_variants_until_one_succeeds(self) -> None:
        client = _VariantClient()
        interaction = generate_content_with_tools(
            client=client, model="gemini-2.5-flash", input_text="query", tool_names=["google_search", "url_context"]
        )
        self.assertEqual(interaction, {"ok": "direct"})
        self.assertGreaterEqual(len(client.calls), 2)
        self.assertEqual(client.calls[0], ["Tool", "Tool"])
        self.assertEqual(client.calls[-1], ["GoogleSearch", "UrlContext"])

    def test_search_web_returns_answer_and_sources_from_interaction(self) -> None:
        structured_text = (
            '{"summary":"Python 3.14 includes updates.","sources":['
            '{"title":"Python Docs","url":"https://docs.python.org/3.14/","description":"Official Python docs"}]}'
        )
        interaction = SimpleNamespace(
            steps=[
                {
                    "type": "model_output",
                    "content": [
                        {
                            "type": "text",
                            "text": structured_text,
                            "annotations": [
                                {"type": "url_citation", "title": "Python Docs", "url": "https://docs.python.org/3.14/"},
                                {"type": "url_citation", "title": "Python Docs", "url": "https://docs.python.org/3.14/"},
                            ],
                        }
                    ],
                }
            ],
            candidates=[],
        )
        settings = SimpleNamespace(project_id="demo-project", google_cloud_location="europe-west1")

        with (
            patch("services.agents_service.chat.tool_handlers.web_search.search.get_settings", return_value=settings),
            patch(
                "services.agents_service.chat.tool_handlers.web_search.search.genai.Client",
                return_value=_FakeClient(interaction),
            ),
        ):
            result = search_web("latest Python 3.14 features", max_results=5, agent_model="gemini-2.5-flash")

        self.assertEqual(result["query"], "latest Python 3.14 features")
        self.assertEqual(result["answer"], "Python 3.14 includes updates.")
        self.assertEqual(len(result["sources"]), 1)
        self.assertEqual(result["sources"][0]["url"], "https://docs.python.org/3.14/")
        self.assertEqual(result["returned"], 1)
        self.assertEqual(result["results"][0]["title"], "Python Docs")
        self.assertIn("verified", result["results"][0])
        self.assertIn("display", result)
        self.assertIn("display_html", result)
        self.assertIn("Sources:", result["display"])

    def test_search_web_uses_candidate_fallback_when_annotations_missing(self) -> None:
        candidate = SimpleNamespace(
            grounding_metadata=SimpleNamespace(
                grounding_chunks=[
                    SimpleNamespace(web=SimpleNamespace(uri="https://example.com/a", title="A")),
                    SimpleNamespace(web=SimpleNamespace(uri="https://example.com/b", title="B")),
                ]
            )
        )
        interaction = SimpleNamespace(
            steps=[{"type": "model_output", "content": [{"type": "text", "text": "Summary", "annotations": []}]}],
            candidates=[candidate],
        )
        settings = SimpleNamespace(project_id="demo-project", google_cloud_location="europe-west1")

        with (
            patch("services.agents_service.chat.tool_handlers.web_search.search.get_settings", return_value=settings),
            patch(
                "services.agents_service.chat.tool_handlers.web_search.search.genai.Client",
                return_value=_FakeClient(interaction),
            ),
        ):
            result = search_web("query", max_results=1)

        self.assertEqual(result["returned"], 1)
        self.assertEqual(result["sources"][0]["title"], "A")
        self.assertEqual(result["sources"][0]["url"], "https://example.com/a")

    def test_search_web_returns_error_when_client_fails(self) -> None:
        settings = SimpleNamespace(project_id="demo-project", google_cloud_location="europe-west1")

        with (
            patch("services.agents_service.chat.tool_handlers.web_search.search.get_settings", return_value=settings),
            patch(
                "services.agents_service.chat.tool_handlers.web_search.search.genai.Client",
                return_value=_FakeClient(interaction=SimpleNamespace(steps=[]), error=RuntimeError("boom")),
            ),
        ):
            result = search_web("query")

        self.assertIn("error", result)
        self.assertIn("boom", result["error"])

    def test_search_web_retries_when_first_response_has_no_sources(self) -> None:
        first = SimpleNamespace(steps=[{"type": "model_output", "content": [{"type": "text", "text": "No citations"}]}], candidates=[])
        second = SimpleNamespace(
            steps=[
                {
                    "type": "model_output",
                    "content": [
                        {
                            "type": "text",
                            "text": "With citation.",
                            "annotations": [{"type": "url_citation", "title": "Example", "url": "https://example.com"}],
                        }
                    ],
                }
            ],
            candidates=[],
        )
        settings = SimpleNamespace(project_id="demo-project", google_cloud_location="europe-west1")
        fake_client = _FakeClient([first, second])

        with (
            patch("services.agents_service.chat.tool_handlers.web_search.search.get_settings", return_value=settings),
            patch("services.agents_service.chat.tool_handlers.web_search.search.genai.Client", return_value=fake_client),
        ):
            result = search_web("query")

        self.assertGreaterEqual(fake_client.models.calls, 2)
        self.assertEqual(result["returned"], 1)
        self.assertEqual(result["sources"][0]["url"], "https://example.com")

    def test_search_web_filters_to_verified_sources_when_available(self) -> None:
        research = SimpleNamespace(
            steps=[
                {
                    "type": "model_output",
                    "content": [
                        {
                            "type": "text",
                            "text": "Draft answer",
                            "annotations": [
                                {"type": "url_citation", "title": "Bad", "url": "https://example.com/bad"},
                                {"type": "url_citation", "title": "Good", "url": "https://example.com/good"},
                            ],
                        }
                    ],
                }
            ],
            candidates=[],
        )
        verify_bad = SimpleNamespace(
            steps=[
                {
                    "type": "model_output",
                    "content": [
                        {"type": "text", "text": '{"supports_answer": false, "confidence": "high", "reason": "irrelevant"}'}
                    ],
                }
            ],
            candidates=[],
        )
        verify_good = SimpleNamespace(
            steps=[
                {
                    "type": "model_output",
                    "content": [
                        {"type": "text", "text": '{"supports_answer": true, "confidence": "high", "reason": "matches"}'}
                    ],
                }
            ],
            candidates=[],
        )
        settings = SimpleNamespace(project_id="demo-project", google_cloud_location="europe-west1")

        with (
            patch("services.agents_service.chat.tool_handlers.web_search.search.get_settings", return_value=settings),
            patch(
                "services.agents_service.chat.tool_handlers.web_search.search.genai.Client",
                return_value=_FakeClient([research, verify_bad, verify_good]),
            ),
        ):
            result = search_web("query", max_results=5)

        self.assertEqual(result["returned"], 1)
        self.assertEqual(result["sources"][0]["url"], "https://example.com/good")
        self.assertTrue(result["results"][0]["verified"])

    def test_search_web_falls_back_when_summary_is_chatty(self) -> None:
        interaction = SimpleNamespace(
            steps=[
                {
                    "type": "model_output",
                    "content": [
                        {
                            "type": "text",
                            "text": "Agent: I have already provided the websites before.\n\nHere they are again.",
                            "annotations": [{"type": "url_citation", "title": "Example", "url": "https://example.com"}],
                        }
                    ],
                }
            ],
            candidates=[],
        )
        settings = SimpleNamespace(project_id="demo-project", google_cloud_location="europe-west1")

        with (
            patch("services.agents_service.chat.tool_handlers.web_search.search.get_settings", return_value=settings),
            patch(
                "services.agents_service.chat.tool_handlers.web_search.search.genai.Client",
                return_value=_FakeClient(interaction),
            ),
        ):
            result = search_web("super-markets in lisbon", max_results=5, agent_model="gemini-2.5-flash")

        self.assertEqual(result["summary"], "Top web results for: super-markets in lisbon")
        self.assertEqual(result["answer"], "Top web results for: super-markets in lisbon")

    def test_search_web_uses_structured_sources_without_annotations(self) -> None:
        interaction = SimpleNamespace(
            steps=[
                {
                    "type": "model_output",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                '{"summary":"Auto shops in Lisbon.","sources":['
                                '{"title":"Save My Car","url":"https://www.savemycar.pt/","description":"Auto repair services"}]}'
                            ),
                            "annotations": [],
                        }
                    ],
                }
            ],
            candidates=[],
        )
        settings = SimpleNamespace(project_id="demo-project", google_cloud_location="europe-west1")

        with (
            patch("services.agents_service.chat.tool_handlers.web_search.search.get_settings", return_value=settings),
            patch(
                "services.agents_service.chat.tool_handlers.web_search.search.genai.Client",
                return_value=_FakeClient(interaction),
            ),
        ):
            result = search_web("auto shops in lisbon", max_results=5)

        self.assertEqual(result["returned"], 1)
        self.assertEqual(result["sources"][0]["url"], "https://www.savemycar.pt/")
        self.assertEqual(result["summary"], "Auto shops in Lisbon.")

    def test_search_web_uses_fallback_summary_for_non_json_answer(self) -> None:
        interaction = SimpleNamespace(
            steps=[
                {
                    "type": "model_output",
                    "content": [
                        {
                            "type": "text",
                            "text": "Here are some auto repair shops in Lisbon and their websites, based on my search:",
                            "annotations": [{"type": "url_citation", "title": "Save My Car", "url": "https://www.savemycar.pt/"}],
                        }
                    ],
                }
            ],
            candidates=[],
        )
        settings = SimpleNamespace(project_id="demo-project", google_cloud_location="europe-west1")

        with (
            patch("services.agents_service.chat.tool_handlers.web_search.search.get_settings", return_value=settings),
            patch(
                "services.agents_service.chat.tool_handlers.web_search.search.genai.Client",
                return_value=_FakeClient(interaction),
            ),
        ):
            result = search_web("car autoshops in lisbon", max_results=5)

        self.assertEqual(result["summary"], "Top web results for: car autoshops in lisbon")
        self.assertEqual(result["answer"], "Top web results for: car autoshops in lisbon")

    def test_search_web_parses_json_inside_markdown_code_block(self) -> None:
        interaction = SimpleNamespace(
            steps=[
                {
                    "type": "model_output",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "```json\n"
                                '{"summary":"Lisbon auto shops","sources":[{"title":"Block28","url":"https://block28.in.net/","description":"Independent shop"}]}\n'
                                "```"
                            ),
                            "annotations": [],
                        }
                    ],
                }
            ],
            candidates=[],
        )
        settings = SimpleNamespace(project_id="demo-project", google_cloud_location="europe-west1")

        with (
            patch("services.agents_service.chat.tool_handlers.web_search.search.get_settings", return_value=settings),
            patch(
                "services.agents_service.chat.tool_handlers.web_search.search.genai.Client",
                return_value=_FakeClient(interaction),
            ),
        ):
            result = search_web("lisbon auto shops")

        self.assertEqual(result["summary"], "Lisbon auto shops")
        self.assertEqual(result["sources"][0]["url"], "https://block28.in.net/")

    def test_format_web_search_response_renders_summary_and_sources(self) -> None:
        formatted = format_web_search_response(
            {
                "summary": "Top websites in Lisbon.",
                "sources": [
                    {
                        "title": "Continente",
                        "url": "https://www.continente.pt/",
                        "description": "Official supermarket website.",
                    }
                ],
            }
        )
        self.assertIn("Top websites in Lisbon.", formatted)
        self.assertIn("Sources:", formatted)
        self.assertIn("https://www.continente.pt/", formatted)

    def test_format_web_search_response_html_renders_clickable_links(self) -> None:
        html_output = format_web_search_response_html(
            {
                "summary": "Top websites in Lisbon.",
                "sources": [
                    {
                        "title": "Continente",
                        "url": "https://www.continente.pt/",
                        "description": "Official supermarket website.",
                    }
                ],
            }
        )
        self.assertIn("Top websites in Lisbon.", html_output)
        self.assertIn('<a href="https://www.continente.pt/"', html_output)
        self.assertIn("Official supermarket website.", html_output)


if __name__ == "__main__":
    unittest.main()
