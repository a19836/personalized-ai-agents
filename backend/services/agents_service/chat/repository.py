from __future__ import annotations

from datetime import datetime, timezone

from google.cloud.firestore_v1.base_query import FieldFilter

from shared.firestore import get_firestore_client


class AgentChatRepository:
    def __init__(self) -> None:
        self._collection = get_firestore_client().collection("agent_chats")

    def list_for_user(self, user_id: str) -> list[dict]:
        docs = self._collection.where(filter=FieldFilter("user_id", "==", user_id)).stream()
        sessions = [self._to_chat_dict(doc.id, doc.to_dict()) for doc in docs]
        sessions.sort(key=lambda item: item.get("updated_at") or item.get("created_at"), reverse=True)
        return sessions

    def get(self, chat_id: str) -> dict | None:
        doc = self._collection.document(chat_id).get()
        if not doc.exists:
            return None
        return self._to_chat_dict(doc.id, doc.to_dict())

    def create(self, user_id: str, agent_id: str, title: str) -> dict:
        now = datetime.now(timezone.utc)
        doc_ref = self._collection.document()
        payload = {
            "id": doc_ref.id,
            "user_id": user_id,
            "agent_id": agent_id,
            "title": title,
            "messages": [],
            "created_at": now,
            "updated_at": now,
        }
        doc_ref.set(payload)
        return self._to_chat_dict(doc_ref.id, payload)

    def update_session_agent(self, chat_id: str, agent_id: str, title: str) -> dict | None:
        doc_ref = self._collection.document(chat_id)
        existing = doc_ref.get()
        if not existing.exists:
            return None
        doc_ref.set(
            {
                "agent_id": agent_id,
                "title": title,
                "updated_at": datetime.now(timezone.utc),
            },
            merge=True,
        )
        saved = doc_ref.get()
        return self._to_chat_dict(saved.id, saved.to_dict())

    def update(self, chat_id: str, values: dict) -> dict | None:
        doc_ref = self._collection.document(chat_id)
        existing = doc_ref.get()
        if not existing.exists:
            return None
        doc_ref.set({**values, "updated_at": datetime.now(timezone.utc)}, merge=True)
        saved = doc_ref.get()
        return self._to_chat_dict(saved.id, saved.to_dict())

    def delete(self, chat_id: str) -> bool:
        doc_ref = self._collection.document(chat_id)
        existing = doc_ref.get()
        if not existing.exists:
            return False
        doc_ref.delete()
        return True

    def append_messages(self, chat_id: str, messages: list[dict]) -> dict | None:
        doc_ref = self._collection.document(chat_id)
        existing = doc_ref.get()
        if not existing.exists:
            return None
        data = self._to_chat_dict(existing.id, existing.to_dict())
        current_messages = data.get("messages")
        merged_messages = [*(current_messages if isinstance(current_messages, list) else []), *messages]
        doc_ref.set(
            {
                "messages": merged_messages,
                "updated_at": datetime.now(timezone.utc),
            },
            merge=True,
        )
        saved = doc_ref.get()
        return self._to_chat_dict(saved.id, saved.to_dict())

    @staticmethod
    def _to_chat_dict(doc_id: str, data: dict | None) -> dict:
        if data is None:
            return {}
        payload = {"id": doc_id, **data}
        messages = payload.get("messages")
        if not isinstance(messages, list):
            payload["messages"] = []
        return payload
