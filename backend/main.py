from services import agents_service
from shared.logging import configure_logging

configure_logging()

from services.articles_service.main import articles_service
from services.auth_service.main import auth_service
from services.users_service.main import users_service
from services.agents_service.main import agents_service

__all__ = ["auth_service", "articles_service", "users_service", "agents_service"]
