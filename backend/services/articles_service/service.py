from __future__ import annotations

from dataclasses import dataclass

from services.articles_service.models import Article, ArticleUpdate
from services.articles_service.repository import ArticleRepository
from shared.logging import get_logger

logger = get_logger(__name__)


class ArticleNotFoundError(Exception):
    pass


@dataclass
class ArticleService:
    repository: ArticleRepository

    def list_articles(self) -> list[Article]:
        logger.debug("Loading article list from repository")
        return [Article.model_validate(item) for item in self.repository.get_all()]

    def get_article(self, article_id: str) -> Article:
        logger.debug("Loading article id=%s from repository", article_id)
        article = self.repository.get(article_id)
        if not article:
            raise ArticleNotFoundError("Article not found")
        return Article.model_validate(article)

    def update_article(self, article_id: str, payload: ArticleUpdate, author: str) -> Article:
        current = self.repository.get(article_id)
        values: dict = {"author": author}
        if current:
            logger.debug("Updating existing article id=%s", article_id)
            values["title"] = payload.title if payload.title is not None else current["title"]
            values["body"] = payload.body if payload.body is not None else current["body"]
        else:
            if payload.title is None or payload.body is None:
                raise ValueError("title and body are required when creating an article")
            logger.debug("Creating new article id=%s", article_id)
            values["title"] = payload.title
            values["body"] = payload.body

        saved = self.repository.save(article_id=article_id, values=values)
        return Article.model_validate(saved)

    def delete_article(self, article_id: str) -> None:
        logger.debug("Deleting article id=%s from repository", article_id)
        deleted = self.repository.delete(article_id)
        if not deleted:
            raise ArticleNotFoundError("Article not found")
