import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import requests
from vertexai import agent_engines

from services.agents_service.admin.default_agents import build_articles_agent
from services.agents_service.chat.service import AgentsService
from shared.config import get_settings
from shared.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


def _login() -> str:
    """Log in with Firebase and return a Firebase ID token."""
    settings = get_settings()
    if not settings.firebase_web_api_key:
        raise RuntimeError("FIREBASE_WEB_API_KEY must be set")

    email = settings.test_email or ""
    password = settings.test_password or ""
    if not email or not password:
        raise RuntimeError("TEST_EMAIL and TEST_PASSWORD must be set")

    url = (
        "https://identitytoolkit.googleapis.com/v1/"
        f"accounts:signInWithPassword?key={settings.firebase_web_api_key}"
    )
    logger.info("Logging in as %s", email)
    resp = requests.post(
        url,
        json={"email": email, "password": password, "returnSecureToken": True},
        timeout=10,
    )
    resp.raise_for_status()
    token = resp.json()["idToken"]
    logger.info("Login successful")
    return token


_service = AgentsService(bearer_token=_login())
root_agent = build_articles_agent(_service)

app = agent_engines.AdkApp(
    agent=root_agent
)


async def main():
    async for event in app.async_stream_query(
        user_id="user1",
        message="Tell me about article-2."
    ):
        print(event)


asyncio.run(main())