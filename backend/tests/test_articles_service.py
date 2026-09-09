from __future__ import annotations

import unittest
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any, cast

from flask import Flask, Response as FlaskResponse, request as flask_request
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.articles_service.main import (  # noqa: E402
    app,
    articles_service,
    get_article_service,
    get_authenticated_user,
)
from services.articles_service.models import Article, ArticleUpdate  # noqa: E402
from shared.auth import AuthenticatedUser  # noqa: E402


class StubArticleService:
    def __init__(self) -> None:
        now = datetime.now(timezone.utc)
        self.article = Article(
            id="article-1",
            title="First article",
            body="Example body",
            author="user-123",
            created_at=now,
            updated_at=now,
        )

    def list_articles(self) -> list[Article]:
        return [self.article]

    def get_article(self, article_id: str) -> Article:
        return self.article.model_copy(update={"id": article_id})

    def update_article(self, article_id: str, payload: ArticleUpdate, author: str) -> Article:
        data = self.article.model_dump()
        data.update(
            {
                "id": article_id,
                "title": payload.title or self.article.title,
                "body": payload.body or self.article.body,
                "author": author,
            }
        )
        return Article.model_validate(data)

    def delete_article(self, article_id: str) -> None:
        return None


class ArticlesServiceFastAPITest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._original_overrides = app.dependency_overrides.copy()
        app.dependency_overrides[get_authenticated_user] = lambda: AuthenticatedUser(
            uid="user-123",
            email="user@example.com",
            claims={},
        )
        app.dependency_overrides[get_article_service] = lambda: StubArticleService()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls) -> None:
        app.dependency_overrides = cls._original_overrides

    def test_healthz_endpoint(self) -> None:
        response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_list_articles_endpoint(self) -> None:
        response = self.client.get("/articles")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["id"], "article-1")

    def test_put_endpoint_accepts_stringified_json_body(self) -> None:
        response = self.client.put(
            "/articles/article-2",
            json='{"title":"bbbb1","body":"bb b b  b12"}',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["title"], "bbbb1")

    def test_openapi_contains_articles_route_metadata(self) -> None:
        response = self.client.get("/openapi.json")
        self.assertEqual(response.status_code, 200)
        schema = response.json()
        self.assertEqual(schema["info"]["title"], "Articles Service")
        self.assertEqual(
            schema["paths"]["/articles/{article_id}"]["put"]["summary"],
            "Create or update an article",
        )

    def test_cloud_function_entrypoint_bridges_to_fastapi(self) -> None:
        flask_app = Flask(__name__)
        with flask_app.test_request_context("/healthz", method="GET"):
            response = articles_service(cast(Any, flask_request)._get_current_object())
        self.assertIsInstance(response, FlaskResponse)
        self.assertEqual(response.status_code, 200)

    def test_cloud_function_entrypoint_preserves_cors_headers(self) -> None:
        flask_app = Flask(__name__)
        with flask_app.test_request_context(
            "/articles",
            method="OPTIONS",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        ):
            response = articles_service(cast(Any, flask_request)._get_current_object())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), "http://localhost:5173")
        self.assertIn("GET", response.headers.get("Access-Control-Allow-Methods", ""))

    def test_cloud_function_entrypoint_preserves_json_body_for_put(self) -> None:
        flask_app = Flask(__name__)
        with flask_app.test_request_context(
            "/articles/article-2",
            method="PUT",
            data='{"title":"bbbb1","body":"bb b b  b12"}',
            content_type="application/json",
        ):
            response = articles_service(cast(Any, flask_request)._get_current_object())
        self.assertEqual(response.status_code, 200)
        self.assertIn('"title":"bbbb1"', response.get_data(as_text=True))

    def test_cloud_function_entrypoint_decodes_stringified_json_body_for_put(self) -> None:
        flask_app = Flask(__name__)
        with flask_app.test_request_context(
            "/articles/article-2",
            method="PUT",
            data='"{\\"title\\":\\"bbbb1\\",\\"body\\":\\"bb b b  b12\\"}"',
            content_type="application/json",
        ):
            response = articles_service(cast(Any, flask_request)._get_current_object())
        self.assertEqual(response.status_code, 200)
        self.assertIn('"title":"bbbb1"', response.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
