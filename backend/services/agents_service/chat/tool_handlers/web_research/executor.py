from __future__ import annotations

import re
from typing import Any

from google import genai
from google.genai.types import HttpOptions

from shared.config import get_settings
from shared.logging import get_logger

from .coverage_evaluator import build_follow_up_queries, needs_more_research
from .info_extractor import extract_items_from_sources
from .models import ExtractedItem, ResearchPlan
from .planner import create_research_plan
from .subpage_discovery import discover_relevant_subpages
from ..web_search.search import search_web

logger = get_logger(__name__)
_URL_RE = re.compile(r"https?://[^\s<>\"]+")


def _dedupe_sources(sources: list[dict[str, str]]) -> list[dict[str, str]]:
    deduped: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in sources:
        url = str(item.get("url") or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        title = str(item.get("title") or url).strip() or url
        deduped.append({"title": title, "url": url})
    return deduped


def _dedupe_items(items: list[ExtractedItem]) -> list[ExtractedItem]:
    deduped: list[ExtractedItem] = []
    seen: set[str] = set()
    for item in items:
        values = [str(item.data.get(key, "")).strip().lower() for key in sorted(item.data.keys())]
        key = "|".join(
            [
                *values,
                (item.source_url or "").strip().lower(),
            ]
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _extract_sources_from_request(user_request: str, max_pages: int) -> list[dict[str, str]]:
    seen: set[str] = set()
    sources: list[dict[str, str]] = []
    for match in _URL_RE.findall(user_request):
        url = match.strip().rstrip(".,;:!?)]}")
        if not url or url in seen:
            continue
        seen.add(url)
        sources.append({"title": url, "url": url})
        if len(sources) >= max_pages:
            break
    return sources


def _build_step_queue(plan: ResearchPlan, user_request: str) -> list[dict[str, str]]:
    queue: list[dict[str, str]] = []
    seen: set[str] = set()

    def _append_step(step_type: str, value: str, title: str | None = None) -> None:
        key = f"{step_type}:{value.strip()}"
        if not value.strip() or key in seen:
            return
        seen.add(key)
        if step_type == "search":
            queue.append({"type": "search", "query": value.strip()})
            return
        queue.append({"type": "extract_from_url", "url": value.strip(), "title": (title or value).strip()})

    for step in plan.execution_steps:
        if step.type == "search" and step.query:
            _append_step("search", step.query)
        elif step.type == "extract_from_url" and step.url:
            _append_step("extract_from_url", step.url, step.title)

    if queue:
        return queue

    for source in _extract_sources_from_request(user_request, plan.max_pages):
        _append_step("extract_from_url", source["url"], source["title"])
    for query in plan.search_queries:
        _append_step("search", query)
    return queue


def _discover_subpage_sources(
    *,
    client: genai.Client,
    model: str,
    query: str,
    base_sources: list[dict[str, str]],
    max_depth: int,
    max_pages: int,
) -> list[dict[str, str]]:
    if max_depth <= 0 or not base_sources:
        return []

    discovered: list[dict[str, str]] = []
    visited = {str(item.get("url") or "").strip().rstrip("/") for item in base_sources if item.get("url")}
    queue: list[tuple[str, int]] = [(str(item["url"]).strip(), 1) for item in base_sources if item.get("url")]

    while queue and len(discovered) + len(base_sources) < max_pages:
        url, depth = queue.pop(0)
        if depth > max_depth:
            continue
        subpages = discover_relevant_subpages(
            client=client,
            model=model,
            query=query,
            source_url=url,
            max_links=min(4, max_pages),
        )
        for subpage_url in subpages:
            normalized = subpage_url.rstrip("/")
            if not normalized or normalized in visited:
                continue
            visited.add(normalized)
            discovered.append({"title": normalized, "url": normalized})
            if depth < max_depth:
                queue.append((normalized, depth + 1))
            if len(discovered) + len(base_sources) >= max_pages:
                break
    return discovered


def _build_client() -> genai.Client:
    settings = get_settings()
    project_id = (settings.project_id or "").strip()
    if not project_id:
        raise ValueError("PROJECT_ID is required for web research.")
    location = (settings.google_cloud_location or "").strip() or "global"
    return genai.Client(
        enterprise=True,
        project=project_id,
        location=location,
        http_options=HttpOptions(api_version="v1"),
    )


def run_research(
    *,
    user_request: str,
    desired_count: int = 30,
    max_results: int = 20,
    max_pages: int = 20,
    max_subpage_depth: int = 1,
    agent_model: str | None = None,
) -> dict[str, Any]:
    normalized_request = user_request.strip()
    if not normalized_request:
        logger.warning("web_research aborted: empty user request")
        return {"error": "Research request is required."}
    logger.info(
        "web_research execution started model=%s desired_count=%s max_results=%s max_pages=%s max_subpage_depth=%s",
        (agent_model or "gemini-2.5-flash").strip(),
        desired_count,
        max_results,
        max_pages,
        max_subpage_depth,
    )

    plan = create_research_plan(
        user_request=normalized_request,
        target_items=desired_count,
        max_results=max_results,
        max_pages=max_pages,
        max_subpage_depth=max_subpage_depth,
        model=agent_model,
    )
    logger.debug(
        "web_research plan created objective=%s query_count=%s extraction_fields=%s target_items=%s max_pages=%s",
        plan.objective,
        len(plan.search_queries),
        [field.name for field in plan.extraction_fields],
        plan.target_items,
        plan.max_pages,
    )

    selected_model = (agent_model or "gemini-2.5-flash").strip()
    client = _build_client()

    searched_queries: list[str] = []
    step_queue = _build_step_queue(plan, normalized_request)
    gathered_sources: list[dict[str, str]] = []
    gathered_items: list[ExtractedItem] = []
    search_rounds = 0

    while step_queue and len(gathered_items) < plan.target_items:
        step = step_queue.pop(0)
        step_type = step.get("type")
        if step_type == "extract_from_url":
            url = str(step.get("url") or "").strip()
            if not url:
                continue
            source = {"title": str(step.get("title") or url).strip() or url, "url": url}
            logger.debug("web_research step=extract_from_url url=%s remaining_steps=%s", url, len(step_queue))
            gathered_sources = _dedupe_sources([*gathered_sources, source])[: plan.max_pages]
            new_items = extract_items_from_sources(
                client=client,
                model=selected_model,
                query=normalized_request,
                sources=[source],
                extraction_fields=plan.extraction_fields,
            )
            if not new_items and plan.max_subpage_depth > 0:
                subpage_sources = _discover_subpage_sources(
                    client=client,
                    model=selected_model,
                    query=normalized_request,
                    base_sources=[source],
                    max_depth=plan.max_subpage_depth,
                    max_pages=plan.max_pages,
                )
                if subpage_sources:
                    gathered_sources = _dedupe_sources([*gathered_sources, *subpage_sources])[: plan.max_pages]
                    subpage_items = extract_items_from_sources(
                        client=client,
                        model=selected_model,
                        query=normalized_request,
                        sources=subpage_sources[: plan.max_pages],
                        extraction_fields=plan.extraction_fields,
                    )
                    new_items = [*new_items, *subpage_items]
            gathered_items = _dedupe_items([*gathered_items, *new_items])
            continue

        query = str(step.get("query") or "").strip()
        if not query:
            continue
        if search_rounds >= 3:
            logger.debug("web_research stopping: max search rounds reached")
            break
        logger.debug(
            "web_research step=search round=%s query=%s remaining_steps=%s gathered_items=%s gathered_sources=%s",
            search_rounds + 1,
            query,
            len(step_queue),
            len(gathered_items),
            len(gathered_sources),
        )
        searched_queries.append(query)
        logger.debug("web_research tool_call=web_search query=%s max_results=%s", query, min(plan.max_results, 5))
        search_payload = search_web(query=query, max_results=min(plan.max_results, 5), agent_model=selected_model)
        search_rounds += 1
        if "error" in search_payload:
            logger.warning(
                "web_research web_search error query=%s error=%s",
                query,
                search_payload.get("error"),
            )
            continue

        current_sources = _dedupe_sources(search_payload.get("sources") or [])
        logger.debug("web_research web_search completed query=%s sources_found=%s", query, len(current_sources))
        if not current_sources:
            continue

        gathered_sources = _dedupe_sources([*gathered_sources, *current_sources])[: plan.max_pages]
        new_items = extract_items_from_sources(
            client=client,
            model=selected_model,
            query=normalized_request,
            sources=current_sources[: plan.max_pages],
            extraction_fields=plan.extraction_fields,
        )
        if not new_items and plan.max_subpage_depth > 0:
            subpage_sources = _discover_subpage_sources(
                client=client,
                model=selected_model,
                query=normalized_request,
                base_sources=current_sources,
                max_depth=plan.max_subpage_depth,
                max_pages=plan.max_pages,
            )
            if subpage_sources:
                gathered_sources = _dedupe_sources([*gathered_sources, *subpage_sources])[: plan.max_pages]
                subpage_items = extract_items_from_sources(
                    client=client,
                    model=selected_model,
                    query=normalized_request,
                    sources=subpage_sources[: plan.max_pages],
                    extraction_fields=plan.extraction_fields,
                )
                new_items = [*new_items, *subpage_items]
        gathered_items = _dedupe_items([*gathered_items, *new_items])
        logger.debug("web_research aggregation updated total_items=%s", len(gathered_items))

        if len(gathered_items) >= plan.target_items:
            logger.debug("web_research stopping: target reached total_items=%s", len(gathered_items))
            break
        if not needs_more_research(plan, gathered_items, searched_queries):
            logger.debug("web_research stopping: coverage evaluator says enough research")
            break
        has_pending_search = any(step.get("type") == "search" and str(step.get("query") or "").strip() for step in step_queue)
        if not has_pending_search and search_rounds < 3:
            missing = max(0, plan.target_items - len(gathered_items))
            follow_up = build_follow_up_queries(normalized_request, searched_queries, missing)
            for follow_up_query in follow_up:
                step_queue.append({"type": "search", "query": follow_up_query})
            logger.debug(
                "web_research added follow-up queries count=%s missing=%s",
                len(follow_up),
                missing,
            )

    final_items = gathered_items[: plan.target_items]
    result = {
        "query": normalized_request,
        "objective": plan.objective,
        "requested_items": plan.target_items,
        "returned_items": len(final_items),
        "search_queries": searched_queries,
        "sources": gathered_sources[: plan.max_pages],
        "items": [item.model_dump(mode="json") for item in final_items],
        "coverage": {
            "enough_items": len(final_items) >= plan.target_items,
            "source_count": len(gathered_sources),
            "subpage_depth_used": plan.max_subpage_depth,
        },
        "plan": plan.model_dump(mode="json"),
    }
    logger.info(
        "web_research execution finished requested_items=%s returned_items=%s source_count=%s rounds=%s",
        plan.target_items,
        len(final_items),
        len(gathered_sources),
        search_rounds,
    )
    return result
