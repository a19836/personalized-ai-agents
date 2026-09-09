from __future__ import annotations

import html
import ipaddress
import re
from typing import Callable
from urllib.parse import urlparse

import requests

from shared.logging import get_logger

logger = get_logger(__name__)

_BLOCKED_HOSTS = {
    "localhost",
    "metadata.google.internal",
}
_SCRIPT_STYLE_RE = re.compile(r"<(script|style|noscript)\b[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
_TITLE_RE = re.compile(r"<title\b[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


def _normalize_max_chars(value: int) -> int:
    return max(500, min(120000, int(value)))


def _is_private_or_blocked_host(hostname: str) -> bool:
    normalized = (hostname or "").strip().lower().rstrip(".")
    if not normalized:
        return True
    if normalized in _BLOCKED_HOSTS:
        return True
    try:
        addr = ipaddress.ip_address(normalized)
    except ValueError:
        return False
    return (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_reserved
        or addr.is_multicast
        or addr.is_unspecified
    )


def _extract_title(raw_html: str) -> str:
    match = _TITLE_RE.search(raw_html)
    if not match:
        return ""
    return _WHITESPACE_RE.sub(" ", html.unescape(match.group(1))).strip()


def _extract_visible_text(raw_html: str) -> str:
    without_scripts = _SCRIPT_STYLE_RE.sub(" ", raw_html)
    text = _TAG_RE.sub(" ", without_scripts)
    return _WHITESPACE_RE.sub(" ", html.unescape(text)).strip()


def fetch_url_content(url: str, max_chars: int = 25000) -> dict:
    candidate = str(url or "").strip()
    if not candidate:
        return {"error": "URL is required."}
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"}:
        return {"error": "Only http/https URLs are supported."}
    if not parsed.netloc:
        return {"error": "URL host is required."}
    if _is_private_or_blocked_host(parsed.hostname or ""):
        return {"error": "Private or restricted hosts are not allowed."}

    limit = _normalize_max_chars(max_chars)
    logger.debug("fetch_url_content request url=%s max_chars=%s", candidate, limit)
    try:
        response = requests.get(
            candidate,
            timeout=20,
            headers={"User-Agent": "personalized-ai-agents/1.0"},
            allow_redirects=True,
        )
        response.raise_for_status()
    except requests.exceptions.HTTPError as exc:
        status_code = exc.response.status_code if exc.response is not None else "unknown"
        body = exc.response.text if exc.response is not None else str(exc)
        logger.warning("fetch_url_content http_error url=%s status=%s", candidate, status_code)
        return {"error": f"HTTP {status_code} while fetching URL: {body[:400]}"}
    except requests.exceptions.RequestException as exc:
        logger.warning("fetch_url_content request_error url=%s error=%s", candidate, exc)
        return {"error": f"Failed to fetch URL: {exc}"}

    content_type = str(response.headers.get("content-type") or "").lower()
    raw_html = response.text or ""
    title = _extract_title(raw_html)
    text = _extract_visible_text(raw_html)
    truncated = len(text) > limit
    text_content = text[:limit]

    logger.debug(
        "fetch_url_content success final_url=%s status=%s content_type=%s text_length=%s truncated=%s",
        response.url,
        response.status_code,
        content_type,
        len(text),
        truncated,
    )
    return {
        "url": response.url,
        "status_code": response.status_code,
        "content_type": content_type,
        "title": title,
        "text_content": text_content,
        "text_length": len(text),
        "truncated": truncated,
    }


def build_fetch_url_content_tool(_) -> Callable:
    return fetch_url_content
