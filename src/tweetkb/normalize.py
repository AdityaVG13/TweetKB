from __future__ import annotations

import re
from urllib.parse import urlparse

UI_LINE_RE = re.compile(
    r"^(reply|reposts?|likes?|views?|bookmark|bookmarks|follow|following|show more|"
    r"show replies|translate post|from |promoted|ad\b|relevant people|"
    r"you might like|subscribe| grok|ask grok).*$",
    re.I,
)
STATUS_LINK_RE = re.compile(r"(?:x\.com|twitter\.com)/[^/]+/status/\d+", re.I)
SCHEME_ONLY_RE = re.compile(r"^https?://$", re.I)
FULL_URL_RE = re.compile(r"^https?://\S+$", re.I)
URL_PIECE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%\-]*$")
CODE_TLDS = {
    "py", "rs", "js", "ts", "tsx", "jsx", "go", "rb", "md", "json", "toml", "lock",
    "c", "cc", "h", "hpp", "java", "kt", "swift", "sh",
}
ELLIPSIS = {"…", "...", "…"}


def urls_from_tweet_text(text: str) -> list[str]:
    """Rebuild URLs X split across tweetText nodes (`https://` then host/path)."""
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    urls: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index].rstrip(".,;")
        if FULL_URL_RE.match(line) and len(line) > len("https://x"):
            if _plausible_http_url(line):
                urls.append(line)
            index += 1
            continue
        if SCHEME_ONLY_RE.match(line) or line.lower() in {"http://", "https://"}:
            scheme = line if line.endswith("//") else f"{line}//"
            pieces: list[str] = []
            index += 1
            while index < len(lines):
                nxt = lines[index].strip()
                if nxt in ELLIPSIS:
                    index += 1
                    break
                if SCHEME_ONLY_RE.match(nxt) or FULL_URL_RE.match(nxt):
                    break
                if " " in nxt:
                    break
                if not URL_PIECE_RE.match(nxt):
                    break
                pieces.append(nxt.rstrip(".,;"))
                index += 1
            if pieces:
                joined = scheme + "".join(pieces)
                if _plausible_http_url(joined):
                    urls.append(joined)
            continue
        index += 1
    return list(dict.fromkeys(urls))


def _plausible_http_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    host = parsed.netloc.lower().removeprefix("www.")
    if "." not in host or host.startswith(".") or host.endswith("."):
        return False
    tld = host.rsplit(".", 1)[-1]
    if tld in CODE_TLDS or not tld.isalpha() or len(tld) < 2:
        return False
    return True


def clean_tweet_text(text: str) -> str:
    """Keep the post body. Drop X chrome that leaks out of article.innerText."""
    lines = [line.strip() for line in (text or "").splitlines()]
    kept: list[str] = []
    for line in lines:
        if not line:
            continue
        if UI_LINE_RE.match(line):
            continue
        if re.fullmatch(r"[\d,.kKmMbB]+", line):
            continue
        kept.append(line)
    return "\n".join(kept).strip()


def display_tweet_text(text: str) -> str:
    """One-line body for humans: join X-split `https://` + host."""
    compact = " ".join((text or "").split())
    return re.sub(r"(https?://)\s+", r"\1", compact)


def outbound_links(links: list[str] | tuple[str, ...], status_url: str = "") -> list[str]:
    """Keep real destinations. Drop X UI/analytics/self links."""
    seen: set[str] = set()
    out: list[str] = []
    status_id = ""
    match = re.search(r"/status/(\d+)", status_url or "")
    if match:
        status_id = match.group(1)
    for url in links:
        if not url or url in seen:
            continue
        try:
            parsed = urlparse(url)
        except ValueError:
            continue
        host = parsed.netloc.lower().removeprefix("www.")
        path = parsed.path or ""
        if host in {"t.co", "pic.twitter.com", "help.x.com"}:
            continue
        if host in {"x.com", "twitter.com", "mobile.twitter.com"}:
            if "/analytics" in path or "/i/bookmarks" in path or "/i/history" in path or path in {"/", "/home", "/explore", "/notifications"}:
                continue
            if path.startswith("/search") or path.startswith("/i/flow") or path.startswith("/intent/"):
                continue
            if status_id and f"/status/{status_id}" in path and "/photo" not in path and "/video" not in path:
                continue
            if re.fullmatch(r"/[^/]+", path or ""):
                continue
        seen.add(url)
        out.append(url)
    return out


def normalize_collected_item(item: dict) -> dict | None:
    status_url = (item.get("status_url") or item.get("url") or "").strip()
    status_id = (item.get("status_id") or "").strip()
    if not status_id:
        match = re.search(r"/status/(\d+)", status_url)
        status_id = match.group(1) if match else ""
    tweet_text = clean_tweet_text(item.get("tweet_text") or item.get("text") or "")
    if not tweet_text:
        tweet_text = clean_tweet_text(item.get("raw_text") or "")
    if not status_id or not tweet_text:
        return None
    handle = (item.get("author_handle") or item.get("handle") or "").lstrip("@")
    name = item.get("author_name") or ""
    if name.startswith("@"):
        name = handle
    return {
        "status_id": status_id,
        "status_url": status_url,
        "author_handle": handle,
        "author_name": name.split("\n")[0].strip(),
        "tweet_text": tweet_text,
        "raw_text": (item.get("raw_text") or tweet_text).strip(),
        "created_at": item.get("created_at") or "",
        "links": outbound_links(tuple(item.get("links") or ()) + tuple(urls_from_tweet_text(tweet_text)), status_url),
        "captured_at": item.get("captured_at") or "",
        "collection_source": item.get("collection_source") or "browser",
    }


def repair_links_from_text(store) -> dict[str, int]:
    """Backfill outbound URLs reconstructed from stored tweet_text. No browser."""
    bookmarks = 0
    urls = 0
    rows = store.conn.execute(
        "SELECT id, status_url, tweet_text FROM bookmarks WHERE is_deleted = 0"
    ).fetchall()
    for row in rows:
        bookmark_id = int(row["id"])
        found = outbound_links(urls_from_tweet_text(row["tweet_text"] or ""), row["status_url"] or "")
        current = [item["url"] for item in store.get_bookmark_links(bookmark_id)]
        kept = [url for url in outbound_links(current, row["status_url"] or "") if _plausible_http_url(url)]
        merged = tuple(dict.fromkeys([*kept, *found]))
        if merged == tuple(current):
            continue
        store.replace_bookmark_links(bookmark_id, merged)
        bookmarks += 1
        urls += len(merged)
    return {"bookmarks": bookmarks, "urls": urls}
