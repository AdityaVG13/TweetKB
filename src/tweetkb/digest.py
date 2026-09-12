from __future__ import annotations

from typing import Any

from .search import NOISE_LINK_HOSTS


def build_digest(store, *, saved_after: str | None = None, limit: int = 20) -> dict[str, Any]:
    where = ["b.is_deleted = 0"]
    params: list[object] = []
    if saved_after:
        where.append("b.captured_at >= ?")
        params.append(saved_after)
    clause = " AND ".join(where)
    total = int(
        store.conn.execute(f"SELECT count(*) AS n FROM bookmarks b WHERE {clause}", params).fetchone()["n"]
    )
    categories = [
        {"slug": row["category_slug"], "count": int(row["n"])}
        for row in store.conn.execute(
            f"""
            SELECT c.category_slug, count(*) AS n
            FROM classifications c
            JOIN bookmarks b ON b.id = c.bookmark_id
            WHERE c.is_primary = 1 AND {clause}
            GROUP BY c.category_slug
            ORDER BY n DESC
            """,
            params,
        )
    ]
    authors = [
        {"handle": row["author_handle"], "count": int(row["n"])}
        for row in store.conn.execute(
            f"""
            SELECT b.author_handle, count(*) AS n
            FROM bookmarks b
            WHERE {clause} AND IFNULL(b.author_handle, '') != ''
            GROUP BY b.author_handle
            ORDER BY n DESC
            LIMIT ?
            """,
            [*params, int(limit)],
        )
    ]
    noise = sorted(NOISE_LINK_HOSTS)
    domains = [
        {"domain": row["domain"], "count": int(row["n"])}
        for row in store.conn.execute(
            f"""
            SELECT l.domain, count(DISTINCT b.id) AS n
            FROM bookmark_links bl
            JOIN links l ON l.id = bl.link_id
            JOIN bookmarks b ON b.id = bl.bookmark_id
            WHERE {clause}
              AND lower(IFNULL(l.domain, '')) NOT IN ({",".join("?" * len(noise))})
            GROUP BY l.domain
            ORDER BY n DESC
            LIMIT ?
            """,
            [*params, *noise, int(limit)],
        )
    ]
    needs_review = int(
        store.conn.execute(
            f"SELECT count(*) AS n FROM bookmarks b WHERE {clause} AND b.needs_review = 1",
            params,
        ).fetchone()["n"]
    )
    unclassified = int(
        store.conn.execute(
            f"""
            SELECT count(*) AS n
            FROM bookmarks b
            WHERE {clause}
              AND NOT EXISTS (
                SELECT 1 FROM classifications c WHERE c.bookmark_id = b.id AND c.is_primary = 1
              )
            """,
            params,
        ).fetchone()["n"]
    )
    thin = int(
        store.conn.execute(
            f"SELECT count(*) AS n FROM bookmarks b WHERE {clause} AND length(trim(b.tweet_text)) < 24",
            params,
        ).fetchone()["n"]
    )
    with_outbound = int(
        store.conn.execute(
            f"""
            SELECT count(*) AS n
            FROM bookmarks b
            WHERE {clause}
              AND EXISTS (
                SELECT 1 FROM bookmark_links bl
                JOIN links l ON l.id = bl.link_id
                WHERE bl.bookmark_id = b.id
                  AND lower(IFNULL(l.domain, '')) NOT IN ({",".join("?" * len(noise))})
              )
            """,
            [*params, *noise],
        ).fetchone()["n"]
    )
    return {
        "total": total,
        "needs_review": needs_review,
        "unclassified": unclassified,
        "thin": thin,
        "with_outbound": with_outbound,
        "categories": categories,
        "domains": domains,
        "authors": authors,
        "top_tags": _top_tags(store, saved_after=saved_after, limit=limit),
    }


def _top_tags(store, *, saved_after: str | None, limit: int) -> list[dict[str, Any]]:
    where = ["b.is_deleted = 0"]
    params: list[object] = []
    if saved_after:
        where.append("b.captured_at >= ?")
        params.append(saved_after)
    rows = store.conn.execute(
        f"""
        SELECT t.name AS tag, count(*) AS n
        FROM bookmark_tags bt
        JOIN tags t ON t.id = bt.tag_id
        JOIN bookmarks b ON b.id = bt.bookmark_id
        WHERE {" AND ".join(where)}
        GROUP BY t.name
        ORDER BY n DESC
        LIMIT ?
        """,
        [*params, int(limit)],
    )
    return [{"tag": row["tag"], "count": int(row["n"])} for row in rows]


def format_digest(payload: dict[str, Any]) -> str:
    lines = [
        f"total {payload['total']}",
        f"needs_review {payload['needs_review']}",
        f"unclassified {payload['unclassified']}",
        f"thin {payload.get('thin', 0)}",
        f"with_outbound {payload.get('with_outbound', 0)}",
        "categories",
    ]
    for item in payload["categories"]:
        lines.append(f"  {item['slug']}\t{item['count']}")
    lines.append("domains")
    for item in payload["domains"]:
        lines.append(f"  {item['domain']}\t{item['count']}")
    lines.append("authors")
    for item in payload["authors"]:
        lines.append(f"  @{item['handle']}\t{item['count']}")
    if payload.get("top_tags"):
        lines.append("tags")
        for item in payload["top_tags"]:
            lines.append(f"  {item['tag']}\t{item['count']}")
    return "\n".join(lines)
