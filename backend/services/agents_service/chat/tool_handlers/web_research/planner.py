from __future__ import annotations

import re
from urllib.parse import urlparse

from google import genai
from google.genai.types import HttpOptions

from shared.config import get_settings
from shared.logging import get_logger

from ..shared import extract_json_object
from .models import ExtractionField, ResearchPlan, ResearchStep

logger = get_logger(__name__)

DEFAULT_GENERIC_FIELDS: list[ExtractionField] = [
    ExtractionField(name="item_name", description="Primary name of the item", type="string"),
    ExtractionField(name="item_summary", description="Short summary of the item", type="string"),
    ExtractionField(name="key_details", description="Most relevant details for the objective", type="string"),
]
_URL_RE = re.compile(r"https?://[^\s<>\"]+")


def _extract_request_urls(user_request: str, max_pages: int) -> list[str]:
    seen: set[str] = set()
    urls: list[str] = []
    for match in _URL_RE.findall(user_request):
        raw_url = match.strip().rstrip(".,;:!?)]}")
        parsed = urlparse(raw_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            continue
        if raw_url in seen:
            continue
        seen.add(raw_url)
        urls.append(raw_url)
        if len(urls) >= max_pages:
            break
    return urls


def _default_execution_steps(user_request: str, search_queries: list[str], max_pages: int) -> list[ResearchStep]:
    steps: list[ResearchStep] = []
    for url in _extract_request_urls(user_request, max_pages):
        steps.append(ResearchStep(type="extract_from_url", url=url, title=url))
    for query in search_queries:
        if not query.strip():
            continue
        steps.append(ResearchStep(type="search", query=query.strip()))
    return steps


def _default_plan(
    user_request: str,
    target_items: int,
    max_results: int,
    max_pages: int,
    max_subpage_depth: int,
) -> ResearchPlan:
    base = user_request.strip()
    queries = [
        base,
        f"{base} official sources",
        f"{base} latest data",
        f"{base} detailed report",
        f"{base} examples",
    ]
    deduped: list[str] = []
    seen: set[str] = set()
    for item in queries:
        key = item.lower().strip()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return ResearchPlan(
        objective=base,
        search_queries=deduped,
        execution_steps=_default_execution_steps(base, deduped, max_pages),
        extraction_fields=DEFAULT_GENERIC_FIELDS,
        target_items=target_items,
        max_results=max_results,
        max_pages=max_pages,
        max_subpage_depth=max_subpage_depth,
        require_verification=True,
        additional_research_allowed=True,
    )


def _build_plan_prompt(
    user_request: str,
    target_items: int,
    max_results: int,
    max_pages: int,
    max_subpage_depth: int,
) -> str:
    return (
        "You are a research planner for web data extraction.\n"
        "Return ONLY JSON matching this schema:\n"
        "{"
        '"objective": string,'
        '"search_queries": string[],'
        '"execution_steps": [{"type":"search|extract_from_url","query": string|null,"url": string|null,"title": string|null}],'
        '"extraction_fields": [{"name": string, "description": string, "type": "string|number|boolean|date"}],'
        '"target_items": number,'
        '"max_results": number,'
        '"max_pages": number,'
        '"max_subpage_depth": number,'
        '"require_verification": boolean,'
        '"additional_research_allowed": boolean'
        "}\n"
        "Rules:\n"
        "- Adapt to the user objective; do not assume a fixed domain.\n"
        "- Use specific web queries likely to return authoritative pages.\n"
        "- Do not invent facts, organizations, or citations.\n"
        "- Prefer neutral, verifiable field definitions over speculative fields.\n"
        "- Keep search_queries between 3 and 8.\n"
        "- If the user provides specific URL(s), include extract_from_url execution_steps for those URL(s).\n"
        "- Use search execution_steps for discovery queries.\n"
        "- Ensure extraction_fields are objective-specific and practical to extract.\n\n"
        f"User request: {user_request}\n"
        f"Target items: {target_items}\n"
        f"Max results: {max_results}\n"
        f"Max pages: {max_pages}\n"
        f"Max subpage depth: {max_subpage_depth}\n"
    )


def create_research_plan(
    user_request: str,
    target_items: int = 30,
    max_results: int = 20,
    max_pages: int = 20,
    max_subpage_depth: int = 1,
    model: str | None = None,
) -> ResearchPlan:
    normalized = user_request.strip()
    if not normalized:
        raise ValueError("Research request is required.")

    settings = get_settings()
    project_id = (settings.project_id or "").strip()
    selected_model = (model or "gemini-2.5-flash").strip()
    location = (settings.google_cloud_location or "").strip() or "global"
    fallback = _default_plan(
        normalized,
        target_items,
        max_results,
        max_pages,
        max_subpage_depth=max_subpage_depth,
    )
    if not project_id:
        return fallback

    try:
        client = genai.Client(
            enterprise=True,
            project=project_id,
            location=location,
            http_options=HttpOptions(api_version="v1"),
        )
        response = client.models.generate_content(
            model=selected_model,
            contents=_build_plan_prompt(
                normalized,
                target_items,
                max_results,
                max_pages,
                max_subpage_depth=max_subpage_depth,
            ),
        )
        payload = extract_json_object((response.text or "").strip())
        if not payload:
            return fallback
        if "target_items" not in payload and "desired_contacts" in payload:
            payload["target_items"] = payload.get("desired_contacts")
        if "max_subpage_depth" not in payload:
            payload["max_subpage_depth"] = max_subpage_depth
        plan = ResearchPlan.model_validate(payload)
        if not plan.execution_steps:
            plan.execution_steps = _default_execution_steps(normalized, plan.search_queries, max_pages)
        if not plan.execution_steps and not plan.search_queries:
            return fallback
        return plan
    except Exception as exc:
        logger.warning("research plan generation failed model=%s: %s", selected_model, exc)
        return fallback
