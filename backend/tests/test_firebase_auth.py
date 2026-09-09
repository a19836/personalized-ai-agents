from __future__ import annotations

import sys
import unittest
from pathlib import Path

import requests
import firebase_admin
from firebase_admin import auth, credentials

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shared.config import get_settings
from shared.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


class FirebaseAuthIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        settings = get_settings()
        cls.settings = settings

        cls.firebase_web_api_key = settings.firebase_web_api_key
        cls.firebase_credentials = settings.firebase_credentials
        cls.test_email = settings.test_email or ""
        cls.test_password = settings.test_password or ""

        if not cls.firebase_web_api_key:
            raise unittest.SkipTest("FIREBASE_WEB_API_KEY not set")
        if not cls.firebase_credentials:
            raise unittest.SkipTest("FIREBASE_CREDENTIALS not set")
        if not cls.test_email or not cls.test_password:
            raise unittest.SkipTest("TEST_EMAIL/TEST_PASSWORD not set")

        if not firebase_admin._apps:
            cred = credentials.Certificate(cls.firebase_credentials)
            firebase_admin.initialize_app(cred)
            logger.info("Firebase Admin SDK initialized successfully")

    def test_login_and_verify_id_token(self) -> None:
        url = (
            "https://identitytoolkit.googleapis.com/v1/"
            f"accounts:signInWithPassword?key={self.firebase_web_api_key}"
        )
        payload = {
            "email": self.test_email,
            "password": self.test_password,
            "returnSecureToken": True,
        }

        logger.info("Signing in with Firebase Authentication email=%s", self.test_email)
        response = requests.post(url, json=payload, timeout=10)
        self.assertEqual(
            response.status_code,
            200,
            f"Firebase Authentication failed: {response.text}",
        )

        login_data = response.json()
        id_token = login_data["idToken"]
        logger.info("Firebase login successful uid=%s", login_data.get("localId"))

        logger.info("Verifying Firebase ID token")
        decoded_token = auth.verify_id_token(id_token)
        logger.info("ID token is valid")
        self.assertEqual(decoded_token["email"], self.test_email)
        self.assertIn("sub", decoded_token)


if __name__ == "__main__":
    unittest.main()
