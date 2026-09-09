from __future__ import annotations

from typing import Any, Annotated, cast

import functions_framework
from fastapi import Body, Depends, FastAPI, HTTPException, Path, Response, status
from fastapi.responses import JSONResponse
from flask import Request, Response as FlaskResponse
from pydantic import ValidationError

from services.articles_service.models import Article, ArticleUpdate
from services.articles_service.repository import ArticleRepository
from services.articles_service.service import ArticleNotFoundError, ArticleService
from shared.auth import AuthenticatedUser
from shared.fastapi import AuthorizationHeader, add_cors_middleware, get_authenticated_user, run_fastapi_as_cloud_function
from shared.http import normalize_json_payload
from shared.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)

ArticleId = Annotated[
    str,
    Path(min_length=1, description="Unique article identifier used in the URL."),
]
ArticlePayload = Annotated[
    ArticleUpdate | str,
    Body(description="Fields to create or update on the target article."),
]

app = FastAPI(
    title="Articles Service",
    summary="Manage article records stored in Firestore.",
    description=(
        "Typed API for listing, reading, creating, updating, and deleting articles. "
        "Protected endpoints require a Firebase bearer token."
    ),
    version="1.0.0",
)
add_cors_middleware(app, allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])


def get_article_service() -> ArticleService:
    return ArticleService(repository=ArticleRepository())


@app.exception_handler(ArticleNotFoundError)
async def handle_article_not_found(_: object, exc: ArticleNotFoundError) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(exc)})


@app.get("/healthz", tags=["System"], summary="Check service health")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.options("/", include_in_schema=False)
@app.options("/{path:path}", include_in_schema=False)
def options_handler(path: str = "") -> Response:
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get(
    "/articles",
    response_model=list[Article],
    tags=["Articles"],
    summary="List articles",
    description="Return every article ordered by the most recently updated first.",
)
def list_articles(
    user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)],
    service: Annotated[ArticleService, Depends(get_article_service)],
) -> list[Article]:
    logger.debug("Listing articles for uid=%s", user.uid)
    articles = service.list_articles()
    logger.info("Listed %s articles for uid=%s", len(articles), user.uid)
    return articles


@app.get(
    "/articles/{article_id}",
    response_model=Article,
    tags=["Articles"],
    summary="Get one article",
    description="Load a single article by its identifier.",
)
def get_article(
    article_id: ArticleId,
    user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)],
    service: Annotated[ArticleService, Depends(get_article_service)],
) -> Article:
    logger.debug("Fetching article id=%s for uid=%s", article_id, user.uid)
    return service.get_article(article_id)


@app.post(
    "/articles/{article_id}",
    response_model=Article,
    tags=["Articles"],
    summary="Create or update an article",
    description="Create the article when it does not exist yet, otherwise update the provided fields.",
)
@app.put(
    "/articles/{article_id}",
    response_model=Article,
    tags=["Articles"],
    summary="Create or update an article",
    description="Create the article when it does not exist yet, otherwise update the provided fields.",
)
def upsert_article(
    article_id: ArticleId,
    payload: ArticlePayload,
    user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)],
    service: Annotated[ArticleService, Depends(get_article_service)],
) -> Article:
    logger.debug("Saving article id=%s for uid=%s", article_id, user.uid)
    try:
        article = service.update_article(
            article_id,
            payload=_parse_article_payload(payload),
            author=user.uid,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    logger.info("Saved article id=%s by uid=%s", article_id, user.uid)
    return article


@app.delete(
    "/articles/{article_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    tags=["Articles"],
    summary="Delete an article",
    description="Remove an article by its identifier.",
)
def delete_article(
    article_id: ArticleId,
    user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)],
    service: Annotated[ArticleService, Depends(get_article_service)],
) -> Response:
    logger.debug("Deleting article id=%s for uid=%s", article_id, user.uid)
    service.delete_article(article_id)
    logger.info("Deleted article id=%s by uid=%s", article_id, user.uid)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@functions_framework.http
def articles_service(request: Request) -> FlaskResponse:
    logger.debug(
        "Articles service request method=%s path=%s",
        request.method.upper(),
        request.path.rstrip("/") or "/",
    )
    return run_fastapi_as_cloud_function(app, request)


def _parse_article_payload(payload: ArticleUpdate | str) -> ArticleUpdate:
    normalized = normalize_json_payload(payload)
    try:
        return ArticleUpdate.model_validate(normalized)
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.errors()) from exc
