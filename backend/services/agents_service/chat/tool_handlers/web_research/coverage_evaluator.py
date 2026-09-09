from __future__ import annotations

from .models import ExtractedItem, ResearchPlan


def needs_more_research(plan: ResearchPlan, items: list[ExtractedItem], searched_queries: list[str]) -> bool:
    if not plan.additional_research_allowed:
        return False
    if len(items) >= plan.target_items:
        return False
    return len(searched_queries) < max(1, len(plan.search_queries) + 2)


def build_follow_up_queries(request: str, searched_queries: list[str], missing_count: int) -> list[str]:
    suffixes = [
        "official source",
        "latest report",
        "public dataset",
        "detailed analysis",
        "documentation",
    ]
    normalized_seen = {value.strip().lower() for value in searched_queries}
    queries: list[str] = []
    for suffix in suffixes:
        query = f"{request} {suffix}".strip()
        if query.lower() in normalized_seen:
            continue
        queries.append(query)
        if len(queries) >= max(1, min(missing_count, 3)):
            break
    return queries
