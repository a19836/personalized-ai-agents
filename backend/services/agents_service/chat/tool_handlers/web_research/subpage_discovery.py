from __future__ import annotations

from urllib.parse import urlparse

from google import genai
from shared.logging import get_logger
from ..shared import extract_json_object, extract_model_text, generate_content_with_url_context

logger = get_logger(__name__)


def _build_discovery_prompt(query: str, source_url: str, max_links: int) -> str:
    return (
        "You are a strict URL discovery assistant.\n"
        "You MUST use url_context to inspect the page before deciding.\n"
        "From the provided page, propose internal sub-pages that are likely to contain information needed for the query.\n"
        "Prefer links such as contact/about/team/research/docs/pricing/news/resources based on relevance.\n"
        "Only include URLs that are explicitly supported by the inspected page context.\n"
        "Do not invent or guess URLs.\n"
        "Return ONLY valid JSON in this schema:\n"
        '{"subpages":[{"url":"https://...","reason":"short reason"}]}\n'
        f"Limit to at most {max_links} subpages.\n"
        "If no relevant sub-pages exist or confidence is low, return {\"subpages\":[]}.\n\n"
        f"User query: {query}\n"
        f"Source URL: {source_url}\n"
    )


def discover_relevant_subpages(
    *,
    client: genai.Client,
    model: str,
    query: str,
    source_url: str,
    max_links: int = 4,
) -> list[str]:
    base = urlparse(source_url)
    base_host = (base.netloc or "").lower()
    if not base_host:
        logger.debug("web_research subpage_discovery skipped invalid base host source_url=%s", source_url)
        return []

    logger.debug(
        "web_research tool_call=url_context action=discover_subpages source_url=%s max_links=%s",
        source_url,
        max_links,
    )
    response = generate_content_with_url_context(
        client=client,
        model=model,
        prompt=_build_discovery_prompt(query=query, source_url=source_url, max_links=max(1, max_links)),
    )
    payload = extract_json_object(extract_model_text(response))
    if not payload:
        logger.debug("web_research subpage_discovery produced no valid JSON source_url=%s", source_url)
        return []

    subpages = payload.get("subpages")
    if not isinstance(subpages, list):
        return []

    urls: list[str] = []
    seen: set[str] = set()
    for item in subpages:
        if not isinstance(item, dict):
            continue
        raw_url = item.get("url")
        if not isinstance(raw_url, str):
            continue
        url = raw_url.strip()
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            continue
        if (parsed.netloc or "").lower() != base_host:
            continue
        normalized = url.rstrip("/")
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        urls.append(normalized)
        if len(urls) >= max(1, max_links):
            break
    logger.debug("web_research subpage_discovery completed source_url=%s discovered=%s", source_url, len(urls))
    return urls
