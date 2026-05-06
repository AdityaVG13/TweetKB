from __future__ import annotations

import subprocess
from dataclasses import dataclass

JUNK_LINK_HOSTS = {
    "business.x.com",
    "help.x.com",
    "ads.twitter.com",
    "analytics.twitter.com",
}

JUNK_LINK_KEYWORDS = {
    "cookie",
    "cookies",
    "privacy",
    "terms",
    "ads",
    "advertising",
    "troubleshooting",
    "login",
    "signup",
}


@dataclass
class JunkCandidate:
    id: int
    status_id: str
    status_url: str
    author_handle: str
    reason: str
    sample: str


def list_junk_candidates(store, limit: int = 50) -> list[JunkCandidate]:
    rows = store.conn.execute(
        """
        SELECT
          b.id,
          b.status_id,
          b.status_url,
          b.author_handle,
          b.tweet_text,
          b.raw_text,
          b.summary,
          GROUP_CONCAT(ce.source_url, ' ') AS enrichment_urls,
          GROUP_CONCAT(ce.title, ' ') AS enrichment_titles,
          MIN(LENGTH(ce.content_text)) AS min_content_chars,
          MAX(LENGTH(ce.content_text)) AS max_content_chars
        FROM bookmarks b
        LEFT JOIN content_enrichments ce ON ce.bookmark_id = b.id
        WHERE b.is_deleted = 0
        GROUP BY b.id
        ORDER BY b.captured_at DESC, b.id DESC
        """
    ).fetchall()
    candidates: list[JunkCandidate] = []
    for row in rows:
        reason = _junk_reason(row)
        if not reason:
            continue
        sample = (row["summary"] or row["tweet_text"] or row["raw_text"] or "").replace("\n", " ")[:180]
        candidates.append(
            JunkCandidate(
                id=int(row["id"]),
                status_id=str(row["status_id"]),
                status_url=str(row["status_url"]),
                author_handle=str(row["author_handle"] or ""),
                reason=reason,
                sample=sample,
            )
        )
        if len(candidates) >= limit:
            break
    return candidates


def open_bookmarks(urls: list[str], browser_app: str = "Google Chrome") -> int:
    opened = 0
    for url in urls:
        subprocess.run(["open", "-a", browser_app, url], check=False)
        opened += 1
    return opened


def _junk_reason(row) -> str:
    text = " ".join(str(row[key] or "") for key in ("enrichment_urls", "enrichment_titles")).lower()
    urls = str(row["enrichment_urls"] or "").lower()
    if any(host in urls for host in JUNK_LINK_HOSTS):
        return "x-ad/help/cookie linked page"
    if any(keyword in text for keyword in JUNK_LINK_KEYWORDS) and int(row["max_content_chars"] or 0) < 1000:
        return "thin policy/login/subscribe page"
    if int(row["min_content_chars"] or 0) and int(row["min_content_chars"] or 0) < 250:
        return "very thin linked content"
    return ""
