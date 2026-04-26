from __future__ import annotations

import hashlib
import re
from pathlib import Path
from urllib.parse import urlparse

STATUS_RE = re.compile(r"(?:x\.com|twitter\.com)/([^/\s]+)/status/(\d+)")
ANY_STATUS_RE = re.compile(r"/status/(\d+)")


def extract_status_id(url: str | None) -> str | None:
    if not url:
        return None
    match = STATUS_RE.search(url) or ANY_STATUS_RE.search(url)
    if not match:
        return None
    return match.group(2) if len(match.groups()) == 2 else match.group(1)


def normalize_status_url(url: str | None, handle: str | None = None, status_id: str | None = None) -> str | None:
    sid = status_id or extract_status_id(url)
    if not sid:
        return url
    parsed_handle = None
    if url:
        match = STATUS_RE.search(url)
        parsed_handle = match.group(1) if match else None
    clean_handle = (handle or parsed_handle or "i").lstrip("@")
    return f"https://x.com/{clean_handle}/status/{sid}"


def slugify(value: str, fallback: str = "bookmark") -> str:
    value = value.strip().lower()
    value = re.sub(r"https?://", "", value)
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value[:90] or fallback


def stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def link_domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().removeprefix("www.")
    except Exception:
        return ""

