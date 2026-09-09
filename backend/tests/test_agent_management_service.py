from __future__ import annotations

import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.agents_service.admin.service import AgentManagementService  # noqa: E402
from services.agents_service.admin.models import AgentTaskAction, AgentTaskPayload  # noqa: E402


class StubRepository:
    def __init__(self) -> None:
        self.deleted_ids: list[str] = []
        self.updated_calls: list[tuple[str, dict]] = []
        self.agent = {
            "id": "agent-1",
            "user_id": "user-1",
            "agent_runtime_resource_name": "projects/p/locations/europe-west1/reasoningEngines/123",
        }

    def get(self, agent_id: str) -> dict | None:
        if agent_id != "agent-1":
            return None
        return dict(self.agent)

    def delete(self, agent_id: str) -> bool:
        self.deleted_ids.append(agent_id)
        return True

    def update(self, agent_id: str, values: dict) -> dict:
        self.updated_calls.append((agent_id, values))
        return {"id": agent_id, **values}


class StubDeployer:
    def __init__(self) -> None:
        self.undeploy_calls: list[str] = []
        self.should_fail = False

    def undeploy(self, resource_name: str) -> None:
        if self.should_fail:
            raise RuntimeError("undeploy failed")
        self.undeploy_calls.append(resource_name)


class StubScheduler:
    def schedule(self, payload: AgentTaskPayload) -> None:
        del payload


class AgentManagementServiceTest(unittest.TestCase):
    def test_undeploy_hard_deletes_only_after_remote_undeploy(self) -> None:
        repo = StubRepository()
        deployer = StubDeployer()
        service = AgentManagementService(repository=repo, deployer=deployer, scheduler=StubScheduler())

        service.process_task(
            AgentTaskPayload(action=AgentTaskAction.UNDEPLOY, agent_id="agent-1", user_id="user-1")
        )

        self.assertEqual(deployer.undeploy_calls, ["projects/p/locations/europe-west1/reasoningEngines/123"])
        self.assertEqual(repo.deleted_ids, ["agent-1"])

    def test_undeploy_failure_does_not_hard_delete(self) -> None:
        repo = StubRepository()
        deployer = StubDeployer()
        deployer.should_fail = True
        service = AgentManagementService(repository=repo, deployer=deployer, scheduler=StubScheduler())

        service.process_task(
            AgentTaskPayload(action=AgentTaskAction.UNDEPLOY, agent_id="agent-1", user_id="user-1")
        )

        self.assertEqual(repo.deleted_ids, [])
        self.assertEqual(len(repo.updated_calls), 1)
        self.assertEqual(repo.updated_calls[0][1]["status"], "FAILED")


if __name__ == "__main__":
    unittest.main()
