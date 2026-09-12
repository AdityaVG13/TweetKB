from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

TOKEN_RE = re.compile(r"[A-Za-z0-9_+\-./]+")
FROM_RE = re.compile(r"(?i)\bfrom:([A-Za-z0-9_]{1,32})")
CAT_RE = re.compile(r"(?i)(?:cat|category):([A-Za-z0-9_-]+)")
LINK_RE = re.compile(r"(?i)\blink:([^\s]+)")
SAVED_RE = re.compile(r"(?i)\bsaved:(\d+)([dw])\b")
NOISE_LINK_HOSTS = {"x.com", "twitter.com", "t.co", "pic.twitter.com", "mobile.twitter.com", "help.x.com"}


@dataclass(frozen=True)
class SearchHit:
    bookmark_id: int
    status_id: str
    status_url: str
    author_handle: str
    tweet_text: str
    snippet: str
    rank: float
    category: str = ""
    outbound_links: tuple[str, ...] = ()
    captured_at: str = ""
    created_at: str = ""


@dataclass
class ParsedQuery:
    text: str
    tokens: list[str] = field(default_factory=list)
    from_handles: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    domains: list[str] = field(default_factory=list)
    saved_days: int | None = None

    def is_empty(self) -> bool:
        return (
            not self.tokens
            and not self.from_handles
            and not self.categories
            and not self.domains
            and self.saved_days is None
        )


def parse_query(query: str) -> ParsedQuery:
    raw = query or ""
    from_handles = [m.group(1).lstrip("@") for m in FROM_RE.finditer(raw)]
    categories = [m.group(1).lower() for m in CAT_RE.finditer(raw)]
    domains = [m.group(1).lower() for m in LINK_RE.finditer(raw)]
    saved_days = None
    saved_match = SAVED_RE.search(raw)
    if saved_match:
        amount = int(saved_match.group(1))
        saved_days = amount if saved_match.group(2).lower() == "d" else amount * 7
    stripped = FROM_RE.sub(" ", raw)
    stripped = CAT_RE.sub(" ", stripped)
    stripped = LINK_RE.sub(" ", stripped)
    stripped = SAVED_RE.sub(" ", stripped)
    tokens = TOKEN_RE.findall(stripped)
    return ParsedQuery(
        text=" ".join(tokens),
        tokens=tokens,
        from_handles=from_handles,
        categories=categories,
        domains=domains,
        saved_days=saved_days,
    )


def fts_query(tokens: list[str]) -> str:
    if not tokens:
        raise ValueError("search query is required")
    return " AND ".join(f'"{token}"' for token in tokens)


def search_bookmarks(
    store,
    query: str,
    limit: int = 50,
    *,
    from_handle: str | None = None,
    category: str | None = None,
    domain: str | None = None,
    sort: str = "rank",
    now: str | None = None,
    saved_after: str | None = None,
) -> list[SearchHit]:
    parsed = parse_query(query)
    if from_handle:
        parsed.from_handles.append(from_handle.lstrip("@"))
    if category:
        parsed.categories.append(category.lower())
    if domain:
        parsed.domains.append(domain.lower())
    if parsed.is_empty():
        raise ValueError("search query is required\nTry: tweetkb search rust --from handle --category coding")

    where = ["b.is_deleted = 0"]
    params: list[object] = []
    tokens = [t.lower() for t in parsed.tokens]
    for token in tokens:
        like = f"%{token}%"
        where.append(
            "(b.tweet_text LIKE ? COLLATE NOCASE OR b.raw_text LIKE ? COLLATE NOCASE "
            "OR IFNULL(b.author_handle,'') LIKE ? COLLATE NOCASE "
            "OR EXISTS (SELECT 1 FROM content_enrichments e WHERE e.bookmark_id = b.id "
            "AND (e.content_text LIKE ? COLLATE NOCASE OR e.title LIKE ? COLLATE NOCASE)) "
            "OR EXISTS (SELECT 1 FROM bookmark_links bl JOIN links l ON l.id = bl.link_id "
            "WHERE bl.bookmark_id = b.id AND (l.url LIKE ? COLLATE NOCASE OR l.domain LIKE ? COLLATE NOCASE)))"
        )
        params.extend([like, like, like, like, like, like, like])

    handles = [h.lower() for h in parsed.from_handles if h]
    if handles:
        placeholders = ",".join("?" * len(handles))
        where.append(f"lower(IFNULL(b.author_handle,'')) IN ({placeholders})")
        params.extend(handles)

    categories = [c for c in parsed.categories if c]
    if categories:
        placeholders = ",".join("?" * len(categories))
        where.append(
            "EXISTS (SELECT 1 FROM classifications c WHERE c.bookmark_id = b.id "
            f"AND c.is_primary = 1 AND c.category_slug IN ({placeholders}))"
        )
        params.extend(categories)

    domains = [d.lstrip("@") for d in parsed.domains if d]
    if domains:
        clauses = []
        for domain in domains:
            clauses.append("(lower(l.domain) = ? OR lower(l.url) LIKE ?)")
            params.extend([domain.lower(), f"%{domain.lower()}%"])
        where.append(
            "EXISTS (SELECT 1 FROM bookmark_links bl JOIN links l ON l.id = bl.link_id "
            f"WHERE bl.bookmark_id = b.id AND ({' OR '.join(clauses)}))"
        )

    cutoff = saved_after
    if parsed.saved_days is not None:
        origin = _as_utc(now)
        cutoff = (origin - timedelta(days=parsed.saved_days)).isoformat()
    if cutoff:
        where.append("b.captured_at >= ?")
        params.append(cutoff)

    mode = (sort or "rank").lower()
    if mode not in {"rank", "saved", "posted"}:
        raise ValueError("sort must be rank, saved, or posted")

    sql = f"""
        SELECT
          b.id,
          b.status_id,
          b.status_url,
          b.author_handle,
          b.tweet_text,
          b.raw_text,
          b.captured_at,
          b.created_at,
          IFNULL((
            SELECT c.category_slug FROM classifications c
            WHERE c.bookmark_id = b.id AND c.is_primary = 1
            LIMIT 1
          ), '') AS category,
          COALESCE(
            (
              SELECT e.content_text FROM content_enrichments e
              WHERE e.bookmark_id = b.id
              ORDER BY e.captured_at DESC LIMIT 1
            ),
            ''
          ) AS enrichment_text,
          COALESCE(
            (
              SELECT group_concat(l.url || ' ' || IFNULL(l.domain, ''), ' ')
              FROM bookmark_links bl JOIN links l ON l.id = bl.link_id
              WHERE bl.bookmark_id = b.id
            ),
            ''
          ) AS link_text,
          COALESCE(
            (
              SELECT group_concat(l.url, char(10))
              FROM bookmark_links bl JOIN links l ON l.id = bl.link_id
              WHERE bl.bookmark_id = b.id
                AND lower(IFNULL(l.domain, '')) NOT IN ('x.com', 'twitter.com', 't.co', 'pic.twitter.com', 'mobile.twitter.com', 'help.x.com')
            ),
            ''
          ) AS outbound
        FROM bookmarks b
        WHERE {' AND '.join(where)}
    """
    rows = store.conn.execute(sql, params).fetchall()
    scores = _fts_scores(store, parsed.tokens)

    ranked: list[tuple[float, int, str, str, SearchHit]] = []
    for row in rows:
        blob = " ".join(
            [
                row["tweet_text"] or "",
                row["raw_text"] or "",
                row["enrichment_text"] or "",
                row["link_text"] or "",
                row["author_handle"] or "",
            ]
        )
        if tokens and not all(_has_token(blob, token) for token in tokens):
            continue
        density = sum(_token_count(blob, token) for token in tokens)
        bookmark_id = int(row["id"])
        fts_rank = scores.get(bookmark_id)
        rank = float(fts_rank) if fts_rank is not None else (100.0 - density)
        snippet_src = row["tweet_text"] or ""
        if tokens and not all(_has_token(snippet_src, token) for token in tokens):
            snippet_src = row["enrichment_text"] or row["link_text"] or blob
        hit = SearchHit(
            bookmark_id=bookmark_id,
            status_id=str(row["status_id"]),
            status_url=row["status_url"] or "",
            author_handle=row["author_handle"] or "",
            tweet_text=row["tweet_text"] or "",
            snippet=_snippet(snippet_src, parsed.text or " ".join(tokens)),
            rank=rank,
            category=row["category"] or "",
            outbound_links=_outbound(row["outbound"] or ""),
            captured_at=row["captured_at"] or "",
            created_at=row["created_at"] or "",
        )
        ranked.append((rank, -density, row["captured_at"] or "", row["created_at"] or "", hit))

    if mode == "saved":
        ranked.sort(key=lambda item: _invert_iso(item[2]))
    elif mode == "posted":
        ranked.sort(key=lambda item: _invert_iso(item[3]))
    else:
        ranked.sort(key=lambda item: (item[0], item[1], _invert_iso(item[2])))
    return [item[4] for item in ranked[: int(limit)]]


def _has_token(blob: str, token: str) -> bool:
    return _token_count(blob, token) > 0


def _token_count(blob: str, token: str) -> int:
    if not token:
        return 0
    return len(re.findall(rf"(?i)(?<![A-Za-z0-9_]){re.escape(token)}(?![A-Za-z0-9_])", blob or ""))


def _outbound(value: str) -> tuple[str, ...]:
    return tuple(item for item in value.split("\n") if item)


def _as_utc(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _invert_iso(value: str) -> str:
    return "".join(chr(255 - ord(ch)) for ch in value) if value else "~"


def _fts_scores(store, tokens: list[str]) -> dict[int, float]:
    if not tokens:
        return {}
    try:
        rows = store.conn.execute(
            "SELECT rowid, bm25(bookmarks_fts) AS rank FROM bookmarks_fts WHERE bookmarks_fts MATCH ?",
            (fts_query(tokens),),
        ).fetchall()
    except sqlite3.OperationalError:
        return {}
    return {int(row["rowid"]): float(row["rank"]) for row in rows}


def _snippet(text: str, query: str, radius: int = 90) -> str:
    compact = " ".join((text or "").split())
    if not compact:
        return ""
    lower = compact.lower()
    needle = (query or "").strip().lower()
    index = lower.find(needle) if needle else 0
    if index < 0:
        for token in TOKEN_RE.findall(needle):
            index = lower.find(token.lower())
            if index >= 0:
                break
    if index < 0:
        return compact[: radius * 2]
    start = max(0, index - 20)
    end = min(len(compact), index + radius)
    prefix = "…" if start else ""
    suffix = "…" if end < len(compact) else ""
    return f"{prefix}{compact[start:end]}{suffix}"
