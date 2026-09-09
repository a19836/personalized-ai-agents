from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse

import requests

from shared.config import get_settings
from shared.logging import get_logger

logger = get_logger(__name__)


def _append_path(base_url: str, suffix: str) -> str:
    parsed = urlparse(base_url)
    base_path = (parsed.path or "").rstrip("/")
    normalized_suffix = suffix if suffix.startswith("/") else f"/{suffix}"
    if base_path.endswith(normalized_suffix):
        final_path = base_path
    else:
        final_path = f"{base_path}{normalized_suffix}"
    return urlunparse(parsed._replace(path=final_path))


def _articles_list_url(base_url: str) -> str:
    return _append_path(base_url, "/articles")


def _article_item_url(base_url: str, article_id: str) -> str:
    return f"{_articles_list_url(base_url).rstrip('/')}/{article_id}"


def _users_me_url(base_url: str) -> str:
    return _append_path(base_url, "/me")


@dataclass
class AgentsService:
    bearer_token: str

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.bearer_token}"}

    def get_article(self, article_id: str) -> dict:
        """Retrieves a single article by its ID from the articles service."""
        settings = get_settings()
        url = _article_item_url(settings.articles_service_url, article_id)
        logger.debug("Fetching article id=%s from %s", article_id, url)
        try:
            resp = requests.get(url, headers=self._auth_headers(), timeout=10)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.HTTPError as exc:
            return {"error": f"HTTP {exc.response.status_code} on {url}: {exc.response.text}"}
        except requests.exceptions.RequestException as exc:
            return {"error": f"Could not reach articles service ({url}): {exc}"}

    def list_articles(self) -> list[dict]:
        """Lists all articles from the articles service."""
        settings = get_settings()
        url = _articles_list_url(settings.articles_service_url)
        timeout_seconds = 10
        logger.info(
            "list_articles request url=%s method=GET params={} timeout=%ss token_present=%s",
            url,
            timeout_seconds,
            bool((self.bearer_token or "").strip()),
        )
        try:
            resp = requests.get(url, headers=self._auth_headers(), timeout=timeout_seconds)
            logger.info(
                "list_articles response url=%s status_code=%s ok=%s",
                url,
                resp.status_code,
                resp.ok,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.HTTPError as exc:
            status_code = exc.response.status_code if exc.response is not None else "unknown"
            response_text = exc.response.text if exc.response is not None else str(exc)
            logger.error("list_articles HTTPError url=%s status_code=%s", url, status_code)
            return [{"error": f"HTTP {status_code} on {url}: {response_text}"}]
        except requests.exceptions.RequestException as exc:
            logger.error("list_articles RequestException url=%s error=%s", url, exc)
            return [{"error": f"Could not reach articles service ({url}): {exc}"}]

    def get_current_user_profile(self) -> dict:
        """Retrieves the current authenticated user profile from the users service."""
        settings = get_settings()
        url = _users_me_url(settings.users_service_url)
        logger.debug("Fetching current user profile from %s", url)
        try:
            resp = requests.get(url, headers=self._auth_headers(), timeout=10)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.HTTPError as exc:
            return {"error": f"HTTP {exc.response.status_code} on {url}: {exc.response.text}"}
        except requests.exceptions.RequestException as exc:
            return {"error": f"Could not reach users service ({url}): {exc}"}

    def update_current_user_profile(
        self,
        display_name: str | None = None,
        role: str | None = None,
    ) -> dict:
        """Updates profile fields for the current authenticated user."""
        payload: dict[str, str | None] = {}
        if display_name is not None:
            payload["display_name"] = display_name
        if role is not None:
            payload["role"] = role
        if not payload:
            return {"error": "At least one field must be provided to update profile"}

        settings = get_settings()
        url = _users_me_url(settings.users_service_url)
        logger.debug("Updating current user profile via %s fields=%s", url, list(payload.keys()))
        try:
            resp = requests.put(url, headers=self._auth_headers(), json=payload, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.HTTPError as exc:
            return {"error": f"HTTP {exc.response.status_code} on {url}: {exc.response.text}"}
        except requests.exceptions.RequestException as exc:
            return {"error": f"Could not reach users service ({url}): {exc}"}

    def web_search(self, query: str, max_results: int = 5, agent_model: str | None = None) -> dict:
        from services.agents_service.chat.tool_handlers.web_search.search import search_web

        return search_web(query=query, max_results=max_results, agent_model=agent_model)

    def web_search_structured(self, query: str, max_results: int = 5, agent_model: str | None = None) -> dict:
        from services.agents_service.chat.tool_handlers.web_search.search import search_web_structured

        return search_web_structured(query=query, max_results=max_results, agent_model=agent_model)

    def web_research(
        self,
        user_request: str,
        desired_count: int = 30,
        max_results: int = 20,
        max_pages: int = 20,
        max_subpage_depth: int = 1,
        agent_model: str | None = None,
    ) -> dict:
        from services.agents_service.chat.tool_handlers.web_research.research import run_web_research

        return run_web_research(
            user_request=user_request,
            desired_count=desired_count,
            max_results=max_results,
            max_pages=max_pages,
            max_subpage_depth=max_subpage_depth,
            agent_model=agent_model,
        )
