from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

from google.cloud import firestore
from google.oauth2 import service_account

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shared.logging import configure_logging, get_logger
from shared.config import get_settings

configure_logging()
logger = get_logger(__name__)


def _resolve_credentials_file() -> str:
    settings = get_settings()
    value = settings.google_application_credentials or settings.firebase_credentials
    if not value:
        raise RuntimeError(
            "Set GOOGLE_APPLICATION_CREDENTIALS or FIREBASE_CREDENTIALS before running this test."
        )

    if value.strip().startswith("{"):
        parsed = json.loads(value)
        path = parsed.get("client_email")
        raise RuntimeError(
            "FIREBASE_CREDENTIALS is JSON text, but this test expects a file path. "
            "Set GOOGLE_APPLICATION_CREDENTIALS to the service-account JSON file path."
        )

    return value


class FirestoreIntegrationTest(unittest.TestCase):
    def test_firestore_round_trip(self) -> None:
        project_id = get_settings().project_id
        self.assertTrue(project_id, "PROJECT_ID must be set")

        credentials_file = _resolve_credentials_file()
        logger.info("Connecting to Firestore project_id=%s", project_id)
        self.assertTrue(
            Path(credentials_file).exists(),
            f"Credentials file not found: {credentials_file}",
        )
        logger.debug("Using credentials file path=%s", credentials_file)

        credentials = service_account.Credentials.from_service_account_file(
            credentials_file
        )
        db = firestore.Client(project=project_id, credentials=credentials)
        logger.info("Connected to Firestore")

        document_ref = db.collection("test").document("hello2")
        logger.debug("Writing Firestore document %s", document_ref.path)
        document_ref.set(
            {
                "message": "Hello Firestore 2!",
                "source": "python-test",
                "success": True,
            }
        )
        logger.info("Document written successfully")

        document = document_ref.get()
        self.assertTrue(document.exists)
        logger.info("Document read successfully")
        self.assertEqual(document.to_dict()["source"], "python-test")


if __name__ == "__main__":
    unittest.main()
