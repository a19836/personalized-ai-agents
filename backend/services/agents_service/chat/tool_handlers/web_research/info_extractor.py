from __future__ import annotations

from typing import Any, Literal, cast

from google import genai

from shared.logging import get_logger

from ..shared import extract_json_object, extract_model_text, generate_content_with_tools
from .models import ExtractedItem, ExtractionField

logger = get_logger(__name__)

def _normalize_confidence(value: object) -> Literal["high", "medium", "low"]:
    if not isinstance(value, str):
        return "low"
    normalized = value.strip().lower()
    if normalized in {"high", "medium", "low"}:
        return normalized
    return "low"


def _build_extraction_input(query: str, source: dict[str, str], extraction_fields: list[ExtractionField]) -> str:
    fields_shape = ", ".join([f"{field.name} ({field.type}): {field.description}" for field in extraction_fields])
    field_names = ", ".join([field.name for field in extraction_fields])
    return (
        "You are a strict information extractor.\n"
        "You MUST inspect the target URL using tools before extracting.\n"
        "Use url_context and/or fetch_url_content as needed.\n"
        "Extract information relevant to the user query from the provided URL.\n"
        "Ground every extracted value in page content from that URL.\n"
        "Return ONLY valid JSON with this schema:\n"
        '{"items": [{ "<field_name>": value, "...": value, "confidence": "high|medium|low" }]}\n'
        "Use field names exactly as requested. Keep missing values as empty strings.\n"
        "Do not fabricate data.\n"
        "Never invent people, companies, emails, phone numbers, URLs, or metrics.\n"
        "If evidence is missing or uncertain, keep that field as an empty string.\n"
        "If no relevant items are found, return {\"items\": []}.\n\n"
        f"User query: {query}\n"
        f"URL: {source['url']}\n"
        f"Expected field names: {field_names}\n"
        f"Preferred fields: {fields_shape}\n"
    )


def _build_tool_choice_input(query: str, source: dict[str, str]) -> str:
    return (
        "You are deciding which tool to use for extracting information from a URL.\n"
        "Return ONLY valid JSON with this schema:\n"
        '{"tool":"url_context|fetch_url_content","reason":"short reason"}\n'
        "Guidance:\n"
        "- Prefer url_context for standard web pages and source verification.\n"
        "- Choose fetch_url_content when the user asks for HTML/text extraction from a specific URL or contact-page details.\n"
        "- Do not include any extra text.\n\n"
        f"User query: {query}\n"
        f"URL: {source['url']}\n"
    )


def _choose_extraction_tool(client: genai.Client, *, model: str, query: str, source: dict[str, str]) -> str:
    prompt = _build_tool_choice_input(query=query, source=source)
    try:
        response = client.models.generate_content(model=model, contents=prompt)
    except Exception:
        response = client.models.generate_content(model=model, contents=[prompt])
    payload = extract_json_object(extract_model_text(response))
    selected = str((payload or {}).get("tool") or "").strip().lower()
    if selected in {"url_context", "fetch_url_content"}:
        return selected
    return "url_context"


def _parse_items(
    payload: dict[str, Any],
    source_url: str,
    extraction_fields: list[ExtractionField],
) -> list[ExtractedItem]:
    items_raw = payload.get("items")
    if not isinstance(items_raw, list):
        return []
    allowed_fields = [field.name for field in extraction_fields]
    items: list[ExtractedItem] = []
    for item in items_raw:
        if not isinstance(item, dict):
            continue
        data: dict[str, Any] = {}
        for field_name in allowed_fields:
            raw_value = item.get(field_name)
            if raw_value is None:
                data[field_name] = ""
            elif isinstance(raw_value, str):
                data[field_name] = raw_value.strip()
            else:
                data[field_name] = raw_value
        if not any(str(value).strip() for value in data.values()):
            continue
        record = ExtractedItem(
            data=data,
            source_url=source_url,
            confidence=cast(Literal["high", "medium", "low"], _normalize_confidence(item.get("confidence"))),
        )
        items.append(record)
    return items


def extract_items_from_sources(
    *,
    client: genai.Client,
    model: str,
    query: str,
    sources: list[dict[str, str]],
    extraction_fields: list[ExtractionField],
    max_items_per_source: int = 8,
) -> list[ExtractedItem]:
    items: list[ExtractedItem] = []
    logger.debug(
        "web_research extraction started sources=%s fields=%s",
        len(sources),
        [field.name for field in extraction_fields],
    )
    for source in sources:
        url = source.get("url", "").strip()
        if not url:
            continue
        extraction_prompt = _build_extraction_input(query=query, source=source, extraction_fields=extraction_fields)
        tool_name = _choose_extraction_tool(client, model=model, query=query, source=source)
        logger.debug("web_research tool_choice selected_tool=%s source_url=%s", tool_name, url)
        try:
            response = generate_content_with_tools(
                client=client,
                model=model,
                input_text=extraction_prompt,
                tool_names=[tool_name],
            )
        except Exception as exc:
            logger.warning(
                "web_research extract_source tool_call_failed tool=%s source_url=%s error=%s",
                tool_name,
                url,
                exc,
            )
            continue
        payload = extract_json_object(extract_model_text(response))
        if not payload:
            logger.debug(
                "web_research extract_source produced no valid JSON tool=%s source_url=%s",
                tool_name,
                url,
            )
            continue
        parsed = _parse_items(payload, source_url=url, extraction_fields=extraction_fields)
        logger.debug(
            "web_research extract_source parsed_items=%s tool=%s source_url=%s",
            len(parsed),
            tool_name,
            url,
        )
        if not parsed:
            continue
        items.extend(parsed[: max(1, max_items_per_source)])
    logger.debug("web_research extraction finished total_items=%s", len(items))
    return items
