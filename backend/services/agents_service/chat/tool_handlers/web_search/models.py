from __future__ import annotations

from pydantic import BaseModel


class WebSource(BaseModel):
    title: str
    url: str
    description: str = ""


class WebSearchResponse(BaseModel):
    query: str
    summary: str
    answer: str
    sources: list[WebSource]
