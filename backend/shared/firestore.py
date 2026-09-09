from __future__ import annotations

from google.cloud import firestore

from shared.config import get_settings
from shared.firebase import initialize_firebase


def get_firestore_client() -> firestore.Client:
    initialize_firebase()
    settings = get_settings()
    if settings.project_id:
        return firestore.Client(project=settings.project_id)
    return firestore.Client()
