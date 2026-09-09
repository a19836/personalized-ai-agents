from __future__ import annotations

from datetime import datetime, timezone

from shared.firestore import get_firestore_client
from shared.logging import get_logger

logger = get_logger(__name__)


class UserRepository:
    def __init__(self) -> None:
        self._collection = get_firestore_client().collection("users")

    def get(self, uid: str) -> dict | None:
        logger.debug("Reading user profile document uid=%s", uid)
        snapshot = self._collection.document(uid).get()
        if not snapshot.exists:
            return None
        data = snapshot.to_dict() or {}
        return {"uid": uid, **data}

    def save(self, uid: str, values: dict) -> dict:
        logger.debug("Writing user profile document uid=%s", uid)
        now = datetime.now(timezone.utc)
        doc_ref = self._collection.document(uid)
        existing = doc_ref.get()

        payload = {
            "uid": uid,
            **values,
            "updated_at": now,
        }
        if not existing.exists:
            payload["created_at"] = now

        doc_ref.set(payload, merge=True)
        saved = doc_ref.get().to_dict() or {}
        return {"uid": uid, **saved}

    def list_all(self) -> list[dict]:
        logger.debug("Listing all user profile documents")
        records: list[dict] = []
        for snapshot in self._collection.stream():
            data = snapshot.to_dict() or {}
            records.append({"uid": snapshot.id, **data})
        return records

    def delete(self, uid: str) -> None:
        logger.debug("Deleting user profile document uid=%s", uid)
        self._collection.document(uid).delete()
