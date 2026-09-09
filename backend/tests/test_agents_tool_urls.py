from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.agents_service.chat.service import (  # noqa: E402
    _article_item_url,
    _articles_list_url,
    _users_me_url,
)


class AgentsToolUrlTest(unittest.TestCase):
    def test_articles_list_url_accepts_service_root(self) -> None:
        self.assertEqual(
            _articles_list_url("https://articles-service-abc-ew.a.run.app"),
            "https://articles-service-abc-ew.a.run.app/articles",
        )

    def test_articles_list_url_accepts_endpoint_base(self) -> None:
        self.assertEqual(
            _articles_list_url("https://articles-service-abc-ew.a.run.app/articles"),
            "https://articles-service-abc-ew.a.run.app/articles",
        )

    def test_article_item_url_accepts_endpoint_base(self) -> None:
        self.assertEqual(
            _article_item_url("https://articles-service-abc-ew.a.run.app/articles", "x1"),
            "https://articles-service-abc-ew.a.run.app/articles/x1",
        )

    def test_users_me_url_accepts_service_root(self) -> None:
        self.assertEqual(
            _users_me_url("https://users-service-abc-ew.a.run.app"),
            "https://users-service-abc-ew.a.run.app/me",
        )

    def test_users_me_url_accepts_endpoint_base(self) -> None:
        self.assertEqual(
            _users_me_url("https://users-service-abc-ew.a.run.app/me"),
            "https://users-service-abc-ew.a.run.app/me",
        )


if __name__ == "__main__":
    unittest.main()
