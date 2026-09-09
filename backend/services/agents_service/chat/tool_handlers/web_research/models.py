from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class ExtractionField(BaseModel):
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    type: Literal["string", "number", "boolean", "date"] = "string"


class ResearchStep(BaseModel):
    type: Literal["search", "extract_from_url"]
    query: str | None = None
    url: str | None = None
    title: str | None = None

    @model_validator(mode="after")
    def _validate_shape(self) -> "ResearchStep":
        if self.type == "search":
            if not isinstance(self.query, str) or not self.query.strip():
                raise ValueError("ResearchStep with type='search' requires query.")
            self.query = self.query.strip()
            self.url = None
            return self
        if not isinstance(self.url, str) or not self.url.strip():
            raise ValueError("ResearchStep with type='extract_from_url' requires url.")
        self.url = self.url.strip()
        if isinstance(self.title, str):
            self.title = self.title.strip() or self.url
        else:
            self.title = self.url
        self.query = None
        return self


class ResearchPlan(BaseModel):
    objective: str = Field(min_length=1)
    search_queries: list[str] = Field(default_factory=list)
    execution_steps: list[ResearchStep] = Field(default_factory=list)
    extraction_fields: list[ExtractionField] = Field(default_factory=list)
    target_items: int = Field(default=30, ge=1, le=100)
    max_results: int = Field(default=20, ge=1, le=50)
    max_pages: int = Field(default=20, ge=1, le=50)
    max_subpage_depth: int = Field(default=1, ge=0, le=3)
    require_verification: bool = True
    additional_research_allowed: bool = True


class ExtractedItem(BaseModel):
    data: dict[str, Any] = Field(default_factory=dict)
    source_url: str = Field(min_length=1)
    confidence: Literal["high", "medium", "low"] = "low"
