from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ArticleUpdate(BaseModel):
    title: str | None = Field(
        None,
        min_length=1,
        max_length=200,
        description="Human-readable article title.",
        examples=["How I organize AI agent workflows"],
    )
    body: str | None = Field(
        None,
        min_length=1,
        description="Article body content in plain text or markdown.",
        examples=["This article explains how the workflow is structured..."],
    )

    @model_validator(mode="after")
    def validate_at_least_one_field(self) -> "ArticleUpdate":
        if self.title is None and self.body is None:
            raise ValueError("At least one field must be provided")
        return self


class Article(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(description="Unique article identifier.")
    title: str = Field(description="Human-readable article title.")
    body: str = Field(description="Article body content.")
    author: str = Field(description="UID of the user who last created or updated the article.")
    created_at: datetime = Field(description="Timestamp when the article was first created.")
    updated_at: datetime = Field(description="Timestamp when the article was last updated.")
