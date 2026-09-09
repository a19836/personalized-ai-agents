from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class Settings:
    project_id: str
    secret_key: str
    frontend_origin: str
    log_level: str
    firebase_credentials: str | None
    google_application_credentials: str | None
    firebase_web_api_key: str | None
    articles_service_url: str
    users_service_url: str
    articles_agent_engine: str | None
    users_agent_engine: str | None
    google_cloud_location: str
    agent_staging_bucket: str | None
    agent_identity_type: str
    agent_runtime_service_account: str | None
    agent_tasks_queue: str | None
    agent_tasks_location: str
    agent_tasks_target_url: str | None
    agent_tasks_service_account: str | None
    agent_tasks_secret: str | None
    openai_api_key: str | None
    openai_base_url: str
    test_email: str | None
    test_password: str | None

    def firebase_credentials_dict(self) -> dict[str, Any] | None:
        if not self.firebase_credentials:
            return None
        value = self.firebase_credentials.strip()
        if not value.startswith("{"):
            return None
        return json.loads(value)

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"), override=False)

    project_id = os.getenv("PROJECT_ID", "").strip()
    logger.info(f"Loading config with PROJECT_ID={project_id if project_id else 'NOT SET'}")
    
    # Read secrets from environment variables
    secret_key = os.getenv("SECRET_KEY", "change-me")
    firebase_web_api_key = os.getenv("FIREBASE_WEB_API_KEY")

    has_secret_key = secret_key and secret_key != "change-me"
    has_firebase_key = bool(firebase_web_api_key)
    
    logger.info(f"Config loaded: secret_key={'loaded' if has_secret_key else 'NOT LOADED'}, firebase_web_api_key={'loaded' if has_firebase_key else 'NOT LOADED'}")

    return Settings(
        project_id=project_id,
        secret_key=secret_key,
        frontend_origin=os.getenv("FRONTEND_ORIGIN", "*").strip() or "*",
        log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper() or "INFO",
        firebase_credentials=os.getenv("FIREBASE_CREDENTIALS"),
        google_application_credentials=os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
        firebase_web_api_key=firebase_web_api_key,
        articles_service_url=os.getenv("ARTICLES_SERVICE_URL", "http://localhost:8092").rstrip("/"),
        users_service_url=os.getenv("USERS_SERVICE_URL", "http://localhost:8093").rstrip("/"),
        articles_agent_engine=os.getenv("ARTICLES_AGENT_ENGINE"),
        users_agent_engine=os.getenv("USERS_AGENT_ENGINE"),
        google_cloud_location=os.getenv("GOOGLE_CLOUD_LOCATION", os.getenv("REGION", "us-central1")).strip(),
        agent_staging_bucket=os.getenv("AGENT_STAGING_BUCKET"),
        agent_identity_type=os.getenv("AGENT_IDENTITY_TYPE", "AGENT_IDENTITY").strip() or "AGENT_IDENTITY",
        agent_runtime_service_account=os.getenv("AGENT_RUNTIME_SERVICE_ACCOUNT"),
        agent_tasks_queue=os.getenv("AGENT_TASKS_QUEUE"),
        agent_tasks_location=os.getenv("AGENT_TASKS_LOCATION", "").strip()
        or os.getenv("GOOGLE_CLOUD_LOCATION", os.getenv("REGION", "us-central1")).strip()
        or "us-central1",
        agent_tasks_target_url=os.getenv("AGENT_TASKS_TARGET_URL"),
        agent_tasks_service_account=os.getenv("AGENT_TASKS_SERVICE_ACCOUNT"),
        agent_tasks_secret=os.getenv("AGENT_TASKS_SECRET"),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").strip().rstrip("/"),
        test_email=(os.getenv("TEST_EMAIL") or "").strip() or None,
        test_password=(os.getenv("TEST_PASSWORD") or "").strip() or None,
    )
