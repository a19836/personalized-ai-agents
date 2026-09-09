from __future__ import annotations

from datetime import datetime, timezone

from google.cloud.firestore_v1.base_query import FieldFilter

from services.agents_service.admin.models import AgentStatus
from shared.firestore import get_firestore_client
from shared.logging import get_logger

logger = get_logger(__name__)


class AgentRepository:
    def __init__(self) -> None:
        self._collection = get_firestore_client().collection("agents")

    def list_for_user(self, user_id: str) -> list[dict]:
        logger.debug("Listing agents for uid=%s", user_id)
        docs = self._collection.where(filter=FieldFilter("user_id", "==", user_id)).stream()
        items = [self._to_dict(doc.id, doc.to_dict()) for doc in docs]
        visible = [item for item in items if item.get("deleted") is not True]
        visible.sort(key=lambda item: item.get("updated_at") or item.get("created_at"), reverse=True)
        return visible

    def get(self, agent_id: str) -> dict | None:
        doc = self._collection.document(agent_id).get()
        if not doc.exists:
            return None
        data = doc.to_dict() or {}
        if data.get("deleted") is True:
            return None
        return self._to_dict(doc.id, data)

    def create(self, user_id: str, values: dict) -> dict:
        now = datetime.now(timezone.utc)
        doc_ref = self._collection.document()
        payload = {
            "id": doc_ref.id,
            **values,
            "user_id": user_id,
            "status": AgentStatus.DRAFT.value,
            "agent_runtime_resource_name": None,
            "last_error": None,
            "deleted": False,
            "created_at": now,
            "updated_at": now,
        }
        doc_ref.set(payload)
        return self._to_dict(doc_ref.id, payload)

    def update(self, agent_id: str, values: dict) -> dict | None:
        doc_ref = self._collection.document(agent_id)
        existing = doc_ref.get()
        if not existing.exists:
            return None

        payload = {
            **values,
            "updated_at": datetime.now(timezone.utc),
        }
        doc_ref.set(payload, merge=True)
        saved = doc_ref.get()
        return self._to_dict(saved.id, saved.to_dict())

    def delete(self, agent_id: str) -> bool:
        logger.debug("Hard deleting agent document id=%s", agent_id)
        doc_ref = self._collection.document(agent_id)
        existing = doc_ref.get()
        if not existing.exists:
            return False
        doc_ref.delete()
        return True

    @staticmethod
    def _to_dict(doc_id: str, data: dict | None) -> dict:
        if data is None:
            return {}
        return {"id": doc_id, **data}

