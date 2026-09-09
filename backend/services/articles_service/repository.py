from __future__ import annotations

from datetime import datetime, timezone

from google.cloud.firestore_v1 import Query

from shared.firestore import get_firestore_client
from shared.logging import get_logger

logger = get_logger(__name__)


class ArticleRepository:
    def __init__(self) -> None:
        self._collection = get_firestore_client().collection("articles")

    def get_all(self) -> list[dict]:
        logger.debug("Reading all articles from Firestore")
        docs = self._collection.order_by("updated_at", direction=Query.DESCENDING).stream()
        return [self._to_dict(doc.id, doc.to_dict()) for doc in docs]

    def get(self, article_id: str) -> dict | None:
        logger.debug("Reading article document id=%s", article_id)
        doc = self._collection.document(article_id).get()
        if not doc.exists:
            return None
        return self._to_dict(doc.id, doc.to_dict())

    def save(self, article_id: str, values: dict) -> dict:
        logger.debug("Writing article document id=%s", article_id)
        now = datetime.now(timezone.utc)
        document_ref = self._collection.document(article_id)
        snapshot = document_ref.get()

        payload = {**values, "updated_at": now}
        if not snapshot.exists:
            payload["created_at"] = now

        document_ref.set(payload, merge=True)
        saved = document_ref.get()
        return self._to_dict(saved.id, saved.to_dict())

    def delete(self, article_id: str) -> bool:
        logger.debug("Deleting article document id=%s", article_id)
        doc = self._collection.document(article_id).get()
        if not doc.exists:
            return False
        self._collection.document(article_id).delete()
        return True

    @staticmethod
    def _to_dict(doc_id: str, data: dict | None) -> dict:
        if data is None:
            return {}
        return {"id": doc_id, **data}
