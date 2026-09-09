from __future__ import annotations

import html
import json
import re
from typing import Any, Callable
from urllib.parse import urlparse

from google import genai
from google.genai.types import HttpOptions

from shared.config import get_settings
from shared.logging import get_logger

from ...service import AgentsService
from ..shared import generate_content_with_tools, service_from_context
from .models import WebSearchResponse, WebSource

logger = get_logger(__name__)
_JSON_CODE_BLOCK_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)

_WEB_RESEARCH_SYSTEM_INSTRUCTION = """
You are a web research agent.

Your job is to answer questions that require information from the public internet.

You must use the available web research tools to answer:
- google_search
- url_context

Always prefer tool-grounded information over prior knowledge for current or changing topics.
When presenting results:
- Provide only the final answer, with no intermediate reasoning or step-by-step narrative.
- Start with a short summary.
- Then provide a list of sources, each with title, URL, and short description.
- Include source URLs from tool citations.
- Do not invent URLs or unsupported claims.
- If sources disagree, say so.
- If reliable sources are unavailable, say so clearly.
""".strip()


def _safe_public_url(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    if not candidate:
        return None
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"}:
        return None
    if not parsed.netloc:
        return None
    return candidate


def _summary_needs_fallback(value: str) -> bool:
    text = (value or "").strip().lower()
    if not text:
        return True
    bad_markers = (
        "already provided",
        "just provided",
        "here they are again",
        "are you looking for",
        "if you are looking for",
        "please let me know",
    )
    return any(marker in text for marker in bad_markers) or "?" in text


def _normalize_description(value: str) -> str:
    text = " ".join((value or "").split())
    if not text:
        return "Relevant source page."
    if text.endswith("?"):
        text = text[:-1].strip()
    if len(text) > 180:
        text = text[:177].rstrip() + "..."
    return text or "Relevant source page."


def _annotation_field(payload: object, field: str) -> object | None:
    if isinstance(payload, dict):
        return payload.get(field)
    return getattr(payload, field, None)


def _extract_text_and_sources_from_interaction(interaction: object) -> tuple[str, list[dict[str, str]]]:
    steps = _annotation_field(interaction, "steps")
    if not isinstance(steps, list):
        direct_text = _annotation_field(interaction, "text")
        answer = direct_text.strip() if isinstance(direct_text, str) else ""
        if not answer:
            candidates = _annotation_field(interaction, "candidates")
            if isinstance(candidates, list):
                for candidate in candidates:
                    content = _annotation_field(candidate, "content")
                    parts = _annotation_field(content, "parts") if content is not None else None
                    if not isinstance(parts, list):
                        continue
                    chunks: list[str] = []
                    for part in parts:
                        part_text = _annotation_field(part, "text")
                        if isinstance(part_text, str) and part_text.strip():
                            chunks.append(part_text.strip())
                    if chunks:
                        answer = "\n".join(chunks).strip()
                        break
        sources = _extract_sources_from_candidates(interaction)
        return answer, sources

    answer_parts: list[str] = []
    sources: list[dict[str, str]] = []
    seen_urls: set[str] = set()

    for step in steps:
        step_type = _annotation_field(step, "type")
        if step_type != "model_output":
            continue

        content_blocks = _annotation_field(step, "content")
        if not isinstance(content_blocks, list):
            continue

        for content_block in content_blocks:
            block_type = _annotation_field(content_block, "type")
            if block_type != "text":
                continue

            text = _annotation_field(content_block, "text")
            if isinstance(text, str) and text.strip():
                answer_parts.append(text.strip())

            annotations = _annotation_field(content_block, "annotations")
            if not isinstance(annotations, list):
                continue

            for annotation in annotations:
                annotation_type = _annotation_field(annotation, "type")
                if annotation_type != "url_citation":
                    continue
                url = _safe_public_url(_annotation_field(annotation, "url"))
                if not url:
                    url = _safe_public_url(_annotation_field(annotation, "uri"))
                if not url:
                    continue
                title = _annotation_field(annotation, "title")
                normalized_title = str(title).strip() if isinstance(title, str) and title.strip() else url
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                sources.append({"title": normalized_title, "url": url})

    return "\n".join(answer_parts).strip(), sources


def _extract_sources_from_candidates(interaction: object) -> list[dict[str, str]]:
    candidates = getattr(interaction, "candidates", None)
    if not isinstance(candidates, list):
        return []

    sources: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for candidate in candidates:
        grounding = getattr(candidate, "grounding_metadata", None)
        chunks = getattr(grounding, "grounding_chunks", None) if grounding is not None else None
        if not isinstance(chunks, list):
            continue
        for chunk in chunks:
            web = getattr(chunk, "web", None)
            if web is None:
                continue
            url = _safe_public_url(getattr(web, "uri", None))
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            title = str(getattr(web, "title", None) or url).strip() or url
            sources.append({"title": title, "url": url})
    return sources


def _build_research_input(query: str, strict_citations: bool) -> str:
    citation_rule = (
        "You must include at least one URL citation in your response."
        if strict_citations
        else "Include URL citations for key claims."
    )
    return (
        f"{_WEB_RESEARCH_SYSTEM_INSTRUCTION}\n\n"
        f"{citation_rule}\n\n"
        "Output requirement:\n"
        "Return ONLY valid JSON (no markdown, no prose outside JSON) using this schema:\n"
        '{\n'
        '  "summary": "short summary only",\n'
        '  "sources": [\n'
        '    {"title": "page title", "url": "https://...", "description": "one-line description"}\n'
        "  ]\n"
        "}\n"
        "- No progress updates or follow-up questions.\n\n"
        f"User query:\n{query}"
    )


def _extract_json_object(raw_text: str) -> dict[str, Any] | None:
    text = raw_text.strip()
    if not text:
        return None
    for candidate in _json_object_candidates(text):
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def _json_object_candidates(raw_text: str) -> list[str]:
    candidates: list[str] = []
    seen: set[str] = set()

    def _add(candidate: str) -> None:
        normalized = candidate.strip()
        if not normalized or normalized in seen:
            return
        seen.add(normalized)
        candidates.append(normalized)

    for match in _JSON_CODE_BLOCK_RE.finditer(raw_text):
        _add(match.group(1))

    _add(raw_text)
    if raw_text.startswith("{") and raw_text.endswith("}"):
        _add(raw_text)

    max_candidates = 20
    starts = [index for index, char in enumerate(raw_text) if char == "{"]
    for start in starts:
        depth = 0
        for end in range(start, len(raw_text)):
            char = raw_text[end]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    _add(raw_text[start : end + 1])
                    if len(candidates) >= max_candidates:
                        return candidates
                    break
            if depth < 0:
                break
    return candidates


def _extract_structured_summary_and_hints(raw_text: str) -> tuple[str, dict[str, dict[str, str]], bool]:
    payload = _extract_json_object(raw_text)
    if not payload:
        return "", {}, False

    summary_text = str(payload.get("summary") or payload.get("answer") or "").strip()
    summary_lines = [line.strip() for line in summary_text.splitlines() if line.strip()]
    summary = summary_lines[0] if summary_lines else ""
    hints_by_url: dict[str, dict[str, str]] = {}
    sources = payload.get("sources")
    if isinstance(sources, list):
        for item in sources:
            if not isinstance(item, dict):
                continue
            url = _safe_public_url(item.get("url"))
            if not url:
                continue
            title = str(item.get("title") or "").strip()
            description = str(item.get("description") or "").strip()
            hints_by_url[url] = {"title": title, "description": description}
    return summary, hints_by_url, True


def _build_verification_input(query: str, answer: str, source: dict[str, str]) -> str:
    return (
        "You are a strict source verifier.\n"
        "You MUST use the url_context tool to inspect the provided URL content before deciding.\n"
        "Decide whether the URL supports the answer for the query.\n"
        "Return ONLY valid JSON with this schema:\n"
        '{"supports_answer": true|false, "confidence": "high|medium|low", "reason": "short source description (max 20 words)"}\n\n'
        f"Query: {query}\n"
        f"Draft answer: {answer}\n"
        f"URL to verify: {source['url']}\n"
    )


def _verify_sources_with_url_context(
    client: genai.Client,
    selected_model: str,
    query: str,
    answer: str,
    sources: list[dict[str, str]],
) -> tuple[list[dict[str, str]], dict[str, dict[str, Any]]]:
    verified_sources: list[dict[str, str]] = []
    verification_by_url: dict[str, dict[str, Any]] = {}
    for source in sources:
        url = source["url"]
        interaction = generate_content_with_tools(
            client=client,
            model=selected_model,
            input_text=_build_verification_input(query=query, answer=answer, source=source),
            tool_names=["url_context"],
        )
        verification_text, _ = _extract_text_and_sources_from_interaction(interaction)
        payload = _extract_json_object(verification_text)
        if not payload:
            verification_by_url[url] = {
                "verified": False,
                "confidence": "low",
                "reason": "",
            }
            continue

        supports_answer = bool(payload.get("supports_answer") is True)
        confidence_raw = payload.get("confidence")
        confidence = str(confidence_raw).lower() if isinstance(confidence_raw, str) else "low"
        if confidence not in {"high", "medium", "low"}:
            confidence = "low"
        reason = str(payload.get("reason") or "").strip()
        if supports_answer and not reason:
            reason = "Relevant source for this query."
        verification_by_url[url] = {
            "verified": supports_answer,
            "confidence": confidence,
            "reason": reason,
        }
        if supports_answer:
            verified_sources.append(source)

    return verified_sources, verification_by_url


def _run_web_research(
    query: str,
    model: str | None = None,
) -> tuple[str, list[dict[str, str]], dict[str, dict[str, Any]], dict[str, dict[str, str]]]:
    settings = get_settings()
    project_id = (settings.project_id or "").strip()
    if not project_id:
        raise ValueError("PROJECT_ID is required for web_search.")

    selected_model = (model or "gemini-2.5-flash").strip()
    location = (settings.google_cloud_location or "").strip() or "global"
    client = genai.Client(
        enterprise=True,
        project=project_id,
        location=location,
        http_options=HttpOptions(api_version="v1"),
    )

    final_answer = ""
    last_sources: list[dict[str, str]] = []
    source_hints_by_url: dict[str, dict[str, str]] = {}
    used_structured_output = False
    for attempt in range(2):
        interaction = generate_content_with_tools(
            client=client,
            model=selected_model,
            input_text=_build_research_input(query, strict_citations=attempt > 0),
            tool_names=["google_search", "url_context"],
        )
        answer, sources = _extract_text_and_sources_from_interaction(interaction)
        if not sources:
            sources = _extract_sources_from_candidates(interaction)
        summary, hints, has_structured_output = _extract_structured_summary_and_hints(answer)
        used_structured_output = used_structured_output or has_structured_output
        if has_structured_output and hints and not sources:
            sources = [{"title": value.get("title") or url, "url": url} for url, value in hints.items()]
        if hints:
            source_hints_by_url = hints
            merged: list[dict[str, str]] = []
            seen_urls: set[str] = set()
            for source in sources:
                source_url = source.get("url")
                if source_url in seen_urls:
                    continue
                seen_urls.add(source_url)
                hint = hints.get(source_url, {})
                merged.append(
                    {
                        "title": str(hint.get("title") or source.get("title") or source_url).strip(),
                        "url": source_url,
                    }
                )
            sources = merged

        final_answer = summary if has_structured_output else ""
        last_sources = sources
        if sources:
            break

        logger.warning(
            "web_search response missing citations query=%s attempt=%s model=%s",
            query,
            attempt + 1,
            selected_model,
        )

    if not last_sources:
        return final_answer, last_sources, {}, source_hints_by_url

    verified_sources, verification_by_url = _verify_sources_with_url_context(
        client=client,
        selected_model=selected_model,
        query=query,
        answer=final_answer,
        sources=last_sources,
    )
    if verified_sources:
        fallback_answer = final_answer if used_structured_output else ""
        return fallback_answer, verified_sources, verification_by_url, source_hints_by_url
    fallback_answer = final_answer if used_structured_output else ""
    return fallback_answer, last_sources, verification_by_url, source_hints_by_url


def search_web_structured(query: str, max_results: int = 5, agent_model: str | None = None) -> dict:
    normalized_query = query.strip()
    if not normalized_query:
        return {"error": "Query is required"}

    try:
        target = max(1, min(int(max_results), 5))
    except (TypeError, ValueError):
        return {"error": "max_results must be a valid integer between 1 and 5."}
    try:
        answer, gathered_sources, verification_by_url, source_hints_by_url = _run_web_research(
            normalized_query, model=agent_model
        )
    except Exception as exc:
        logger.warning("web_search failed query=%s error=%s", normalized_query, exc)
        return {"error": f"Web search failed: {exc}"}
    if not gathered_sources:
        return {"error": "Web search failed: model response did not include any source citations."}

    selected_sources = gathered_sources[:target]
    summary_text = (answer or "").strip()
    summary_lines = [line.strip() for line in summary_text.splitlines() if line.strip()]
    summary = summary_lines[0] if summary_lines else ""
    if _summary_needs_fallback(summary):
        summary = f"Top web results for: {normalized_query}"
    results: list[dict[str, Any]] = []
    for index, source in enumerate(selected_sources, start=1):
        url = source["url"]
        domain = urlparse(url).netloc
        hint = source_hints_by_url.get(url) or {}
        verification_reason = str((verification_by_url.get(url) or {}).get("reason") or "").strip()
        description = _normalize_description(verification_reason or str(hint.get("description") or "").strip())
        title = str(hint.get("title") or source["title"]).strip() or source["title"]
        results.append(
            {
                "rank": index,
                "title": title,
                "url": url,
                "domain": domain,
                "description": description,
                "content_preview": description,
                "verified": bool((verification_by_url.get(url) or {}).get("verified")),
                "verification_confidence": (verification_by_url.get(url) or {}).get("confidence", ""),
            }
        )

    response_model = WebSearchResponse(
        query=normalized_query,
        summary=summary,
        answer=summary,
        sources=[
            WebSource(
                title=str((source_hints_by_url.get(item["url"]) or {}).get("title") or item["title"]).strip() or item["title"],
                url=item["url"],
                description=(
                    _normalize_description(
                        str((verification_by_url.get(item["url"]) or {}).get("reason") or "").strip()
                        or str((source_hints_by_url.get(item["url"]) or {}).get("description") or "").strip()
                    )
                ),
            )
            for item in selected_sources
        ],
    )
    response = response_model.model_dump(mode="json")
    response.update(
        {
            "requested": target,
            "returned": len(results),
            "opened_pages": len(selected_sources),
            "grounded_candidates": len(gathered_sources),
            "results": results,
        }
    )
    return response


def format_web_search_response(payload: dict[str, Any]) -> str:
    if "error" in payload:
        return str(payload["error"])

    summary_text = str(payload.get("summary") or payload.get("answer") or "").strip()
    summary_lines = [line.strip() for line in summary_text.splitlines() if line.strip()]
    summary = summary_lines[0] if summary_lines else ""
    sources = payload.get("sources")
    if not isinstance(sources, list):
        sources = []

    lines: list[str] = []
    if summary:
        lines.append(summary)
    if sources:
        lines.append("")
        lines.append("Sources:")
        for source in sources:
            if not isinstance(source, dict):
                continue
            title = str(source.get("title") or source.get("url") or "Source").strip()
            url = str(source.get("url") or "").strip()
            description = str(source.get("description") or "").strip()
            if url:
                lines.append(f"- {title}: {url}")
            else:
                lines.append(f"- {title}")
            if description:
                lines.append(f"  {description}")
    return "\n".join(lines).strip()


def format_web_search_response_html(payload: dict[str, Any]) -> str:
    if "error" in payload:
        return f"<p>{html.escape(str(payload['error']))}</p>"

    summary_text = str(payload.get("summary") or payload.get("answer") or "").strip()
    summary_lines = [line.strip() for line in summary_text.splitlines() if line.strip()]
    summary = summary_lines[0] if summary_lines else ""
    sources = payload.get("sources")
    if not isinstance(sources, list):
        sources = []

    summary_html = f"<p>{html.escape(summary)}</p>" if summary else ""
    items: list[str] = []
    for source in sources:
        if not isinstance(source, dict):
            continue
        title = str(source.get("title") or source.get("url") or "Source").strip()
        url = str(source.get("url") or "").strip()
        description = str(source.get("description") or "").strip()
        title_html = html.escape(title)
        url_html = html.escape(url)
        description_html = html.escape(description or "Relevant source page.")
        link_html = (
            f'<a href="{url_html}" target="_blank" rel="noopener noreferrer">{title_html}</a>'
            if url
            else f"<span>{title_html}</span>"
        )
        items.append(
            (
                '<li class="search-result-item">'
                f"<div>{link_html}</div>"
                f'<div class="search-result-description">{description_html}</div>'
                "</li>"
            )
        )
    if not items:
        return summary_html
    return (
        f"{summary_html}<ul class=\"search-results\">"
        + "".join(items)
        + "</ul>"
    )


def search_web(query: str, max_results: int = 5, agent_model: str | None = None) -> dict:
    structured = search_web_structured(query=query, max_results=max_results, agent_model=agent_model)
    return {
        **structured,
        "display": format_web_search_response(structured),
        "display_html": format_web_search_response_html(structured),
    }


def build_web_search_tool(service: AgentsService, agent_model: str | None = None) -> Callable:
    def web_search(query: str, tool_context, max_results: int = 5) -> dict:
        scoped = service_from_context(service, tool_context)
        return scoped.web_search(query=query, max_results=max_results, agent_model=agent_model)

    return web_search
