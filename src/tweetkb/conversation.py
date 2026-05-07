from __future__ import annotations

import re
from typing import Any

QUESTION_RE = re.compile(
    r"\b("
    r"any recommendations|recommendations for|does anyone|can anyone|what are|what is|what's|whats|"
    r"how do|how would|how should|which .* should|should i|best .* for|looking for|"
    r"what tools|what app|what library|what framework"
    r")\b",
    re.IGNORECASE,
)

QUESTION_STARTS = (
    "what ",
    "what's ",
    "whats ",
    "how ",
    "why ",
    "who ",
    "which ",
    "where ",
    "when ",
    "does ",
    "do ",
    "is ",
    "are ",
    "can ",
    "could ",
    "should ",
    "anyone ",
    "recommend ",
    "looking for ",
)


def looks_like_question(text: str) -> bool:
    compact = " ".join((text or "").split())
    if not compact:
        return False
    lead = compact[:500].lower()
    if "?" in lead:
        return True
    return lead.startswith(QUESTION_STARTS) or bool(QUESTION_RE.search(lead))


def should_capture_conversation(bookmark_text: str, payload: dict[str, Any], mode: str = "auto") -> bool:
    if mode == "never":
        return False
    items = _conversation_items(payload)
    if len(items) < 2:
        return False
    if mode == "always":
        return True
    return looks_like_question(bookmark_text)


def format_conversation_context(
    payload: dict[str, Any],
    max_items: int = 12,
    max_chars: int = 6000,
) -> str:
    items = _conversation_items(payload)
    if len(items) < 2:
        return ""
    lines = ["X thread/reply context"]
    for item in items[:max_items]:
        role = item.get("role") or "context"
        handle = item.get("author_handle") or ""
        url = item.get("status_url") or ""
        text = _truncate(_clean_text(item.get("text") or ""), 900)
        if not text:
            continue
        header = f"[{role}]"
        if handle:
            header += f" @{handle.lstrip('@')}"
        if url:
            header += f" {url}"
        lines.extend([header, text, ""])
    formatted = "\n".join(lines).strip()
    return _truncate(formatted, max_chars)


def _conversation_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw_items = payload.get("conversation_items") or []
    if not isinstance(raw_items, list):
        return []
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        text = _clean_text(raw.get("text") or "")
        if not text:
            continue
        key = raw.get("status_url") or text[:140]
        if key in seen:
            continue
        seen.add(key)
        items.append({**raw, "text": text})
    return items


def _clean_text(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", (text or "").strip())


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "."
