from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Callable

from services.agents_service.admin.models import AgentTaskPayload
from shared.config import get_settings
from shared.logging import get_logger

logger = get_logger(__name__)


@dataclass
class AgentTaskScheduler:
    local_handler: Callable[[AgentTaskPayload], None]

    def schedule(self, payload: AgentTaskPayload) -> None:
        settings = get_settings()
        queue_name = (settings.agent_tasks_queue or "").strip()
        target_url = (settings.agent_tasks_target_url or "").strip()
        task_secret = (settings.agent_tasks_secret or "").strip()

        if queue_name and target_url and task_secret:
            self._schedule_cloud_task(
                queue_name=queue_name,
                location=settings.agent_tasks_location,
                target_url=target_url,
                task_secret=task_secret,
                task_service_account=(settings.agent_tasks_service_account or "").strip() or None,
                payload=payload,
            )
            return

        thread = threading.Thread(target=self.local_handler, args=(payload,), daemon=True)
        thread.start()
        logger.info("Scheduled local agent task action=%s agent_id=%s", payload.action, payload.agent_id)

    @staticmethod
    def _schedule_cloud_task(
        *,
        queue_name: str,
        location: str,
        target_url: str,
        task_secret: str,
        task_service_account: str | None,
        payload: AgentTaskPayload,
    ) -> None:
        from google.cloud import tasks_v2
        from google.protobuf import timestamp_pb2

        settings = get_settings()
        if not settings.project_id:
            raise ValueError("PROJECT_ID is required to enqueue Cloud Tasks")

        client = tasks_v2.CloudTasksClient()
        parent = client.queue_path(settings.project_id, location, queue_name)
        body = payload.model_dump_json().encode("utf-8")
        task: dict = {
            "http_request": {
                "http_method": tasks_v2.HttpMethod.POST,
                "url": target_url,
                "headers": {
                    "Content-Type": "application/json",
                    "X-Agents-Task-Secret": task_secret,
                },
                "body": body,
            }
        }
        if task_service_account:
            task["http_request"]["oidc_token"] = {"service_account_email": task_service_account}

        schedule_time = timestamp_pb2.Timestamp()
        schedule_time.GetCurrentTime()
        task["schedule_time"] = schedule_time
        client.create_task(parent=parent, task=task)
        logger.info("Enqueued Cloud Task action=%s agent_id=%s queue=%s", payload.action, payload.agent_id, queue_name)
