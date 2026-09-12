from __future__ import annotations

from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Any, Iterable

from .digest import build_digest
from .search import NOISE_LINK_HOSTS

DEFAULT_KINDS = ("url", "domain", "author")
KIND_NAMES = {
    "url": "same_url",
    "domain": "same_domain",
    "author": "same_author",
    "cat": "same_cat",
}
KIND_RANK = {"same_url": 0, "same_domain": 1, "same_author": 2, "same_cat": 3}


@dataclass(frozen=True)
class RelatedHit:
    bookmark_id: int
    status_id: str
    status_url: str
    author_handle: str
    tweet_text: str
    category: str
    kind: str
    via: str


def parse_kinds(raw: str | Iterable[str] | None) -> tuple[str, ...]:
    if raw is None:
        return DEFAULT_KINDS
    if isinstance(raw, str):
        parts = [item.strip().lower() for item in raw.replace(",", " ").split() if item.strip()]
    else:
        parts = [str(item).strip().lower() for item in raw if str(item).strip()]
    if not parts:
        return DEFAULT_KINDS
    unknown = [item for item in parts if item not in KIND_NAMES]
    if unknown:
        raise ValueError(f"unknown relation kind: {unknown[0]}\nTry: url, domain, author, cat")
    return tuple(parts)


def related_bookmarks(
    store,
    status_id: str,
    *,
    kinds: Iterable[str] | None = None,
    limit: int = 20,
) -> list[RelatedHit]:
    center = store.conn.execute(
        "SELECT id, status_id FROM bookmarks WHERE status_id = ? AND is_deleted = 0",
        (status_id,),
    ).fetchone()
    if not center:
        raise ValueError(f"no bookmark with status_id {status_id}")
    selected = parse_kinds(kinds)
    hits: list[RelatedHit] = []
    for kind in selected:
        hits.extend(_hits_for_kind(store, int(center["id"]), kind))
    strongest: dict[str, RelatedHit] = {}
    for hit in sorted(hits, key=lambda item: KIND_RANK.get(item.kind, 9)):
        strongest.setdefault(hit.status_id, hit)
    ranked = sorted(strongest.values(), key=lambda item: (KIND_RANK.get(item.kind, 9), item.status_id))
    return ranked[: int(limit)]


def author_map(store, handle: str, *, limit: int = 20) -> dict[str, Any]:
    needle = (handle or "").lstrip("@")
    if not needle:
        raise ValueError("author handle is required\nTry: tweetkb map --from HANDLE")
    rows = list(
        store.conn.execute(
            """
            SELECT b.id, b.status_id, b.tweet_text
            FROM bookmarks b
            WHERE b.is_deleted = 0 AND lower(IFNULL(b.author_handle, '')) = lower(?)
            ORDER BY b.captured_at DESC
            """,
            (needle,),
        )
    )
    if not rows:
        raise ValueError(f"no bookmarks from @{needle}")
    ids = [int(row["id"]) for row in rows]
    noise = sorted(NOISE_LINK_HOSTS)
    placeholders = ",".join("?" * len(ids))
    domains = [
        {"domain": row["domain"], "count": int(row["n"])}
        for row in store.conn.execute(
            f"""
            SELECT l.domain, count(DISTINCT b.id) AS n
            FROM bookmark_links bl
            JOIN links l ON l.id = bl.link_id
            JOIN bookmarks b ON b.id = bl.bookmark_id
            WHERE b.id IN ({placeholders})
              AND lower(IFNULL(l.domain, '')) NOT IN ({",".join("?" * len(noise))})
            GROUP BY l.domain
            ORDER BY n DESC
            LIMIT ?
            """,
            [*ids, *noise, int(limit)],
        )
    ]
    categories = [
        {"slug": row["category_slug"], "count": int(row["n"])}
        for row in store.conn.execute(
            f"""
            SELECT c.category_slug, count(*) AS n
            FROM classifications c
            WHERE c.is_primary = 1 AND c.bookmark_id IN ({placeholders})
            GROUP BY c.category_slug
            ORDER BY n DESC
            """,
            ids,
        )
    ]
    return {
        "handle": needle,
        "total": len(rows),
        "domains": domains,
        "categories": categories,
    }


def atlas_payload(store, *, limit: int = 20) -> dict[str, Any]:
    digest = build_digest(store, limit=limit)
    return {
        "total": digest["total"],
        "needs_review": digest["needs_review"],
        "unclassified": digest["unclassified"],
        "categories": digest["categories"],
        "domains": digest["domains"],
        "authors": digest["authors"],
    }


def format_related(center: dict[str, Any], hits: list[RelatedHit]) -> str:
    lines = [
        f"{center['status_id']}  @{center.get('author_handle') or '-'}  {center.get('category') or '-'}",
    ]
    if not hits:
        lines.append("no related bookmarks")
        return "\n".join(lines)
    current = None
    for hit in hits:
        if hit.kind != current:
            current = hit.kind
            lines.append(f"{hit.kind}  {hit.via}")
        handle = f"@{hit.author_handle}" if hit.author_handle else "-"
        text = " ".join((hit.tweet_text or "").split())[:80]
        lines.append(f"  {hit.status_id}  {handle}  {text}")
    return "\n".join(lines)


def format_author_map(payload: dict[str, Any]) -> str:
    lines = [f"@{payload['handle']}  {payload['total']}"]
    for item in payload.get("domains") or []:
        lines.append(f"  {item['domain']}  {item['count']}")
    for item in payload.get("categories") or []:
        lines.append(f"  {item['slug']}  {item['count']}")
    return "\n".join(lines)


def write_atlas(store, out_path: Path, *, limit: int = 20) -> Path:
    payload = atlas_payload(store, limit=limit)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_atlas_html(payload), encoding="utf-8")
    return out_path


def render_atlas_html(payload: dict[str, Any]) -> str:
    categories = payload.get("categories") or []
    domains = payload.get("domains") or []
    authors = payload.get("authors") or []
    circles: list[str] = []
    labels: list[str] = []
    x = 70
    for item in categories[:8]:
        count = int(item["count"])
        r = max(14, min(56, int(8 + (count ** 0.5) * 1.4)))
        slug = escape(str(item["slug"]))
        circles.append(
            f'<circle cx="{x}" cy="110" r="{r}" fill="#1c1e1a" stroke="#3a3e36" data-id="cat-{slug}"/>'
        )
        labels.append(f'<text x="{x}" y="106" text-anchor="middle">{slug}</text>')
        labels.append(f'<text x="{x}" y="120" text-anchor="middle">{count}</text>')
        x += r * 2 + 24
    x = 70
    for item in domains[:6]:
        count = int(item["count"])
        r = max(10, min(28, int(6 + (count ** 0.5))))
        domain = escape(str(item["domain"]))
        circles.append(
            f'<circle cx="{x}" cy="250" r="{r}" fill="#141612" stroke="#c9a227" data-id="dom-{domain}"/>'
        )
        labels.append(f'<text x="{x}" y="254" text-anchor="middle">{domain.split(".")[0][:8]}</text>')
        x += r * 2 + 28
    x = 70
    for item in authors[:6]:
        count = int(item["count"])
        r = max(10, min(22, int(6 + (count ** 0.5))))
        handle = escape(str(item["handle"]))
        circles.append(
            f'<circle cx="{x}" cy="340" r="{r}" fill="#141612" stroke="#6e9e7a" data-id="auth-{handle}"/>'
        )
        labels.append(f'<text x="{x}" y="344" text-anchor="middle">@{handle[:8]}</text>')
        x += r * 2 + 28
    facts = json_preview(payload)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>TweetKB atlas</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background:#0e0f0d; color:#cfd4c8; font:12px/1.4 ui-monospace, SFMono-Regular, Menlo, monospace; }}
  header, footer {{ border-bottom:1px solid #2a2d27; padding:8px 14px; letter-spacing:.14em; text-transform:uppercase; font-size:10px; color:#757a70; display:flex; justify-content:space-between; }}
  footer {{ border-bottom:0; border-top:1px solid #2a2d27; }}
  svg {{ width:100%; height:420px; display:block; }}
  text {{ fill:#8a9084; font-size:10px; letter-spacing:1.2px; text-transform:uppercase; pointer-events:none; }}
  circle {{ cursor:pointer; }}
  aside {{ padding:12px 14px; border-top:1px solid #2a2d27; color:#8a9084; }}
</style>
</head>
<body>
<header><span>tweetkb atlas</span><span>total {payload.get("total", 0)}</span><span>static · no server</span></header>
<svg viewBox="0 0 900 380">{"".join(circles)}{"".join(labels)}</svg>
<aside id="ins">packed categories, then domains, then authors. click a mass. idle cpu ~ 0.</aside>
<footer><span>needs_review {payload.get("needs_review", 0)}</span><span>unclassified {payload.get("unclassified", 0)}</span></footer>
<script>
const facts = {facts};
const ins = document.getElementById("ins");
document.querySelectorAll("circle").forEach(c => c.onclick = () => {{
  ins.textContent = c.getAttribute("data-id") + " · " + JSON.stringify(facts).slice(0, 180);
}});
</script>
</body>
</html>
"""


def json_preview(payload: dict[str, Any]) -> str:
    import json

    return json.dumps(
        {
            "total": payload.get("total"),
            "categories": payload.get("categories"),
            "domains": payload.get("domains"),
            "authors": payload.get("authors"),
        },
        ensure_ascii=True,
    )


def _hits_for_kind(store, bookmark_id: int, kind: str) -> list[RelatedHit]:
    noise = sorted(NOISE_LINK_HOSTS)
    noise_sql = ",".join("?" * len(noise))
    if kind == "url":
        rows = store.conn.execute(
            f"""
            SELECT b.id, b.status_id, b.status_url, b.author_handle, b.tweet_text, l.url AS via,
                   IFNULL((SELECT c.category_slug FROM classifications c WHERE c.bookmark_id = b.id AND c.is_primary = 1 LIMIT 1), '') AS category
            FROM bookmark_links mine
            JOIN bookmark_links other ON other.link_id = mine.link_id AND other.bookmark_id != mine.bookmark_id
            JOIN links l ON l.id = mine.link_id
            JOIN bookmarks b ON b.id = other.bookmark_id
            WHERE mine.bookmark_id = ? AND b.is_deleted = 0
              AND lower(IFNULL(l.domain, '')) NOT IN ({noise_sql})
            """,
            (bookmark_id, *noise),
        )
        return [_row_to_hit(row, "same_url") for row in rows]
    if kind == "domain":
        rows = store.conn.execute(
            f"""
            SELECT b.id, b.status_id, b.status_url, b.author_handle, b.tweet_text, l.domain AS via,
                   IFNULL((SELECT c.category_slug FROM classifications c WHERE c.bookmark_id = b.id AND c.is_primary = 1 LIMIT 1), '') AS category
            FROM bookmark_links mine
            JOIN links mine_l ON mine_l.id = mine.link_id
            JOIN links l ON lower(l.domain) = lower(mine_l.domain) AND l.id != mine_l.id
            JOIN bookmark_links other ON other.link_id = l.id AND other.bookmark_id != mine.bookmark_id
            JOIN bookmarks b ON b.id = other.bookmark_id
            WHERE mine.bookmark_id = ? AND b.is_deleted = 0
              AND lower(IFNULL(mine_l.domain, '')) NOT IN ({noise_sql})
            """,
            (bookmark_id, *noise),
        )
        return [_row_to_hit(row, "same_domain") for row in rows]
    if kind == "author":
        rows = store.conn.execute(
            """
            SELECT b.id, b.status_id, b.status_url, b.author_handle, b.tweet_text, b.author_handle AS via,
                   IFNULL((SELECT c.category_slug FROM classifications c WHERE c.bookmark_id = b.id AND c.is_primary = 1 LIMIT 1), '') AS category
            FROM bookmarks mine
            JOIN bookmarks b ON lower(IFNULL(b.author_handle,'')) = lower(IFNULL(mine.author_handle,''))
              AND b.id != mine.id
            WHERE mine.id = ? AND b.is_deleted = 0 AND IFNULL(mine.author_handle,'') != ''
            """,
            (bookmark_id,),
        )
        return [_row_to_hit(row, "same_author") for row in rows]
    if kind == "cat":
        rows = store.conn.execute(
            """
            SELECT b.id, b.status_id, b.status_url, b.author_handle, b.tweet_text, c.category_slug AS via,
                   c.category_slug AS category
            FROM classifications mine
            JOIN classifications c ON c.category_slug = mine.category_slug AND c.is_primary = 1 AND c.bookmark_id != mine.bookmark_id
            JOIN bookmarks b ON b.id = c.bookmark_id
            WHERE mine.bookmark_id = ? AND mine.is_primary = 1 AND b.is_deleted = 0
            """,
            (bookmark_id,),
        )
        return [_row_to_hit(row, "same_cat") for row in rows]
    return []


def _row_to_hit(row, kind: str) -> RelatedHit:
    return RelatedHit(
        bookmark_id=int(row["id"]),
        status_id=str(row["status_id"]),
        status_url=row["status_url"] or "",
        author_handle=row["author_handle"] or "",
        tweet_text=row["tweet_text"] or "",
        category=row["category"] or "",
        kind=kind,
        via=row["via"] or "",
    )
