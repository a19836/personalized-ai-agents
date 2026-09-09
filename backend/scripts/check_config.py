import os

os.environ["PROJECT_ID"] = "personalized-ai-agents-572b3"

from shared.config import get_settings

settings = get_settings()
print(f"PROJECT_ID: {settings.project_id}")
print(
    f"FIREBASE_WEB_API_KEY: "
    f"{settings.firebase_web_api_key[:20] if settings.firebase_web_api_key else 'NONE'}..."
)
print(
    f"SECRET_KEY: "
    f"{settings.secret_key[:20] if settings.secret_key != 'change-me' else 'DEFAULT'}..."
)
