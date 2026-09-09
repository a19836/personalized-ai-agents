from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.agents_service.admin.agent_deployer import _run_vertex_delete  # noqa: E402


class AgentDeployerDeleteTest(unittest.TestCase):
    def test_run_vertex_delete_uses_force_when_supported(self) -> None:
        calls: list[tuple[str, dict]] = []

        def fake_delete(resource_name: str, *, force: bool = False, **kwargs) -> None:
            calls.append((resource_name, {"force": force, **kwargs}))

        fake_agent_engines = types.SimpleNamespace(delete=fake_delete)
        fake_vertexai = types.SimpleNamespace(agent_engines=fake_agent_engines)

        original_vertexai = sys.modules.get("vertexai")
        sys.modules["vertexai"] = fake_vertexai  # type: ignore[assignment]
        try:
            _run_vertex_delete("projects/p/locations/l/reasoningEngines/1")
        finally:
            if original_vertexai is None:
                del sys.modules["vertexai"]
            else:
                sys.modules["vertexai"] = original_vertexai

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], "projects/p/locations/l/reasoningEngines/1")
        self.assertTrue(calls[0][1]["force"])


if __name__ == "__main__":
    unittest.main()
