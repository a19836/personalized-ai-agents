from __future__ import annotations

import os
import unittest
from datetime import datetime, timezone
from pathlib import Path
import sys
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import patch

from fastapi.testclient import TestClient
from flask import Flask, Response as FlaskResponse, request as flask_request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.agents_service import main as agents_main  # noqa: E402
from services.agents_service.chat import main as chat_main  # noqa: E402
from services.agents_service.chat.service import AgentsService  # noqa: E402
from shared.auth import AuthenticatedUser  # noqa: E402
from shared.config import get_settings  # noqa: E402


_STUB_USER = AuthenticatedUser(uid="user-123", email="user@example.com", claims={})
_STUB_SERVICE = AgentsService(bearer_token="stub-token")


class FakeGeminiResponse:
    text = "Hello from Gemini"


class FakeGeminiModels:
    def generate_content(self, model: str, contents: str) -> FakeGeminiResponse:
        assert model == "gemini-2.5-flash"
        assert isinstance(contents, str)
        return FakeGeminiResponse()


class FakeGeminiClient:
    models = FakeGeminiModels()


class FakeOpenAIResponse:
    def __init__(self, content: str, status_code: int = 200) -> None:
        self.status_code = status_code
        self.ok = status_code < 400
        self.content = b"{}"
        self._content = content

    def json(self) -> dict[str, object]:
        if self.ok:
            return {"choices": [{"message": {"content": self._content}}]}
        return {"error": {"message": self._content}}


class StubManagementService:
    def __init__(self) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self.agents = [
            {
                "id": "agent-1",
                "user_id": "user-123",
                "name": "Articles Assistant",
                "description": "Helps with articles",
                "model": "gemini-2.5-flash",
                "instruction": "Summarize my articles",
                "tools": ["list_articles", "get_article"],
                "config": {},
                "status": "DRAFT",
                "agent_runtime_resource_name": None,
                "last_error": None,
                "created_at": now,
                "updated_at": now,
            }
        ]
        self.deploy_requests: list[str] = []
        self.delete_requests: list[str] = []

    def list_agents(self, user: AuthenticatedUser) -> list[dict[str, Any]]:
        del user
        return self.agents

    def create_agent(self, user: AuthenticatedUser, payload: Any) -> dict[str, Any]:
        del user
        data = payload.model_dump()
        now = datetime.now(timezone.utc).isoformat()
        created = {
            "id": "agent-2",
            "user_id": "user-123",
            **data,
            "config": data.get("config") or {},
            "status": "DRAFT",
            "agent_runtime_resource_name": None,
            "last_error": None,
            "created_at": now,
            "updated_at": now,
        }
        return created

    def get_agent(self, user: AuthenticatedUser, agent_id: str) -> Any:
        del user
        if agent_id == "dynamic-ready":
            class ReadyStatus:
                value = "READY"

            class Obj:
                id = "dynamic-ready"
                name = "Dynamic Agent"
                status = ReadyStatus()
                agent_runtime_resource_name = "projects/p/locations/europe-west1/reasoningEngines/999"

            return Obj()
        return self.agents[0]

    def update_agent(self, user: AuthenticatedUser, agent_id: str, payload: Any) -> dict[str, Any]:
        del user, agent_id
        updates = payload.model_dump(exclude_unset=True)
        merged = {**self.agents[0], **updates}
        return merged

    def request_deploy(self, user: AuthenticatedUser, agent_id: str) -> None:
        del user
        self.deploy_requests.append(agent_id)

    def request_delete(self, user: AuthenticatedUser, agent_id: str) -> None:
        del user
        self.delete_requests.append(agent_id)

    def process_task(self, payload: Any) -> None:
        del payload
        return None


class StubChatRepository:
    def __init__(self) -> None:
        now = datetime.now(timezone.utc)
        self._sessions: dict[str, dict[str, Any]] = {
            "chat-1": {
                "id": "chat-1",
                "user_id": "user-123",
                "agent_id": "agent-1",
                "title": "Articles Assistant chat",
                "messages": [
                    {
                        "role": "user",
                        "text": "Hello",
                        "agent_id": "agent-1",
                        "created_at": now,
                    }
                ],
                "created_at": now,
                "updated_at": now,
            }
        }
        self._counter = 1

    def list_for_user(self, user_id: str) -> list[dict]:
        return [value for value in self._sessions.values() if value.get("user_id") == user_id]

    def get(self, chat_id: str) -> dict | None:
        return self._sessions.get(chat_id)

    def create(self, user_id: str, agent_id: str, title: str) -> dict:
        self._counter += 1
        chat_id = f"chat-{self._counter}"
        now = datetime.now(timezone.utc)
        payload = {
            "id": chat_id,
            "user_id": user_id,
            "agent_id": agent_id,
            "title": title,
            "messages": [],
            "created_at": now,
            "updated_at": now,
        }
        self._sessions[chat_id] = payload
        return payload

    def update_session_agent(self, chat_id: str, agent_id: str, title: str) -> dict | None:
        payload = self._sessions.get(chat_id)
        if payload is None:
            return None
        payload["agent_id"] = agent_id
        payload["title"] = title
        payload["updated_at"] = datetime.now(timezone.utc)
        return payload

    def update(self, chat_id: str, values: dict) -> dict | None:
        payload = self._sessions.get(chat_id)
        if payload is None:
            return None
        payload.update(values)
        payload["updated_at"] = datetime.now(timezone.utc)
        return payload

    def append_messages(self, chat_id: str, messages: list[dict]) -> dict | None:
        payload = self._sessions.get(chat_id)
        if payload is None:
            return None
        payload["messages"] = [*(payload.get("messages") or []), *messages]
        payload["updated_at"] = datetime.now(timezone.utc)
        return payload

    def delete(self, chat_id: str) -> bool:
        if chat_id not in self._sessions:
            return False
        del self._sessions[chat_id]
        return True


class AgentsServiceFastAPITest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._original_openai_api_key = os.environ.get("OPENAI_API_KEY")
        os.environ["OPENAI_API_KEY"] = "test-openai-key"
        get_settings.cache_clear()
        cls._original_get_gemini_client = agents_main.get_gemini_client
        cls._original_run_deployed_agent_query = chat_main._run_deployed_agent_query
        cls.stub_management = StubManagementService()
        cls.stub_chat_repository = StubChatRepository()
        agents_main.get_gemini_client = lambda: FakeGeminiClient()
        chat_main._run_deployed_agent_query = lambda **kwargs: {
            "agent_id": kwargs["agent_id"],
            "message": kwargs["message"],
            "response": "Reply from deployed agent",
            "runtime_session_id": "runtime-1",
        }
        agents_main.app.dependency_overrides[agents_main.get_authenticated_user] = lambda: _STUB_USER
        agents_main.app.dependency_overrides[agents_main.get_agents_service] = lambda: _STUB_SERVICE
        agents_main.app.dependency_overrides[agents_main.get_management_service] = lambda: cls.stub_management
        agents_main.app.dependency_overrides[agents_main.get_chat_repository] = lambda: cls.stub_chat_repository
        cls.client = TestClient(agents_main.app)

    @classmethod
    def tearDownClass(cls) -> None:
        if cls._original_openai_api_key is None:
            os.environ.pop("OPENAI_API_KEY", None)
        else:
            os.environ["OPENAI_API_KEY"] = cls._original_openai_api_key
        get_settings.cache_clear()
        agents_main.get_gemini_client = cls._original_get_gemini_client
        chat_main._run_deployed_agent_query = cls._original_run_deployed_agent_query
        agents_main.app.dependency_overrides.clear()

    def test_list_agents_endpoint(self) -> None:
        response = self.client.get("/agents")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["id"], "agent-1")

    def test_create_agent_endpoint(self) -> None:
        response = self.client.post(
            "/agents",
            json={
                "name": "Users Assistant",
                "description": "Help with profile operations",
                "model": "gemini-2.5-flash",
                "instruction": "Read and update my profile",
                "tools": ["users"],
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "DRAFT")
        self.assertEqual(response.json()["name"], "Users Assistant")

    def test_update_agent_endpoint(self) -> None:
        response = self.client.put("/agents/agent-1", json={"description": "Updated description"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["description"], "Updated description")

    def test_deploy_endpoint_returns_accepted(self) -> None:
        response = self.client.post("/agents/agent-1/deploy")
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["status"], "DEPLOYING")
        self.assertIn("agent-1", self.stub_management.deploy_requests)

    def test_delete_endpoint_returns_accepted(self) -> None:
        response = self.client.delete("/agents/agent-1")
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["status"], "UNDEPLOYING")
        self.assertIn("agent-1", self.stub_management.delete_requests)

    def test_list_chat_sessions_endpoint(self) -> None:
        response = self.client.get("/agents/chat/sessions")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertGreaterEqual(len(data), 1)
        matched = [item for item in data if item["id"] == "chat-1"]
        self.assertEqual(len(matched), 1)
        self.assertTrue(isinstance(matched[0]["agent_id"], str) and bool(matched[0]["agent_id"]))

    def test_get_chat_session_endpoint(self) -> None:
        response = self.client.get("/agents/chat/sessions/chat-1")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["id"], "chat-1")
        self.assertEqual(data["messages"][0]["text"], "Hello")

    def test_create_chat_session_endpoint(self) -> None:
        response = self.client.post("/agents/chat/sessions", json={"agent_id": "gemini"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["agent_id"], "gemini")

    def test_delete_chat_session_endpoint(self) -> None:
        created = self.client.post("/agents/chat/sessions", json={"agent_id": "gemini"})
        self.assertEqual(created.status_code, 200)
        chat_id = created.json()["id"]
        response = self.client.delete(f"/agents/chat/sessions/{chat_id}")
        self.assertEqual(response.status_code, 204)

        missing = self.client.get(f"/agents/chat/sessions/{chat_id}")
        self.assertEqual(missing.status_code, 404)

    def test_agents_chat_endpoint_routes_to_gpt(self) -> None:
        with patch("services.agents_service.chat.main.requests.post", return_value=FakeOpenAIResponse("Reply from GPT")):
            response = self.client.post(
                "/agents/chat",
                json={"agent_id": agents_main.AGENT_GPT, "message": "Hello", "session_id": "chat-1"},
            )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["agent_id"], agents_main.AGENT_GPT)
        self.assertEqual(payload["model"], "gpt-5")
        self.assertEqual(payload["response"], "Reply from GPT")

    def test_available_agents_contains_gpt_default(self) -> None:
        response = self.client.get("/agents/available")
        self.assertEqual(response.status_code, 200)
        ids = [item["id"] for item in response.json()["agents"]]
        self.assertIn("gemini", ids)
        self.assertIn(agents_main.AGENT_GPT, ids)

    def test_available_agents_hides_gpt_when_openai_key_missing(self) -> None:
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}, clear=False):
            get_settings.cache_clear()
            response = self.client.get("/agents/available")
        get_settings.cache_clear()
        self.assertEqual(response.status_code, 200)
        ids = [item["id"] for item in response.json()["agents"]]
        self.assertIn("gemini", ids)
        self.assertNotIn(agents_main.AGENT_GPT, ids)

    def test_agents_chat_routes_to_dynamic_deployed_agent(self) -> None:
        response = self.client.post(
            "/agents/chat",
            json={"agent_id": "dynamic-ready", "message": "Hi", "session_id": "chat-1"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["agent_id"], "dynamic-ready")
        self.assertEqual(response.json()["response"], "Reply from deployed agent")
        self.assertEqual(response.json()["session_id"], "chat-1")

    def test_agents_chat_prefers_display_html_from_json_response_string(self) -> None:
        with patch(
            "services.agents_service.chat.main._run_deployed_agent_query",
            return_value={
                "agent_id": "dynamic-ready",
                "message": "tire shops in lisbon",
                "response": '{"display_html":"<p>Top web results for: tire shops in lisbon</p>","display":"Top web results"}',
                "runtime_session_id": "runtime-2",
            },
        ):
            response = self.client.post(
                "/agents/chat",
                json={"agent_id": "dynamic-ready", "message": "tire shops in lisbon", "session_id": "chat-1"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["agent_id"], "dynamic-ready")
        self.assertEqual(response.json()["response"], "<p>Top web results for: tire shops in lisbon</p>")

    def test_cloud_function_entrypoint_bridges_to_fastapi(self) -> None:
        flask_app = Flask(__name__)
        with flask_app.test_request_context("/healthz", method="GET"):
            response = agents_main.agents_service(cast(Any, flask_request)._get_current_object())
        self.assertIsInstance(response, FlaskResponse)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"status": "ok"})


class AgentResponseExtractionTests(unittest.TestCase):
    def test_extract_preferred_tool_display_reads_nested_response(self) -> None:
        payload = {
            "content": {
                "parts": [
                    {
                        "function_response": {
                            "name": "web_search",
                            "response": {
                                "display_html": "<p>Top web results for: auto shops in Lisbon</p>",
                                "display": "Top web results for: auto shops in Lisbon\n\nSources:\n- Example: https://example.com"
                            },
                        }
                    }
                ]
            }
        }
        responses = chat_main._collect_deployed_function_responses(payload)
        display = chat_main._extract_preferred_tool_display(responses)
        self.assertEqual(display, "<p>Top web results for: auto shops in Lisbon</p>")

    def test_extract_preferred_tool_display_prefers_latest_response(self) -> None:
        responses = [
            {"display": "older"},
            {"display": "newer"},
        ]
        display = chat_main._extract_preferred_tool_display(responses)
        self.assertEqual(display, "newer")

    def test_extract_display_from_payload_falls_back_to_display(self) -> None:
        payload = {"display": "plain display"}
        self.assertEqual(chat_main._extract_display_from_payload(payload), "plain display")

    def test_extract_display_from_object_payload(self) -> None:
        payload = SimpleNamespace(
            content=SimpleNamespace(
                parts=[
                    SimpleNamespace(
                        function_response={
                            "response": {
                                "display_html": "<p>Structured html output</p>",
                                "display": "Structured text output",
                            }
                        }
                    )
                ]
            )
        )
        self.assertEqual(chat_main._extract_display_from_payload(payload), "<p>Structured html output</p>")


if __name__ == "__main__":
    unittest.main()
