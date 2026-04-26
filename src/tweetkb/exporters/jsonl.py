from __future__ import annotations

import json
from pathlib import Path


def export_jsonl(
    store,
    out_path: Path,
    include_categories: set[str] | None = None,
    exclude_categories: set[str] | None = None,
    exclude_review: bool = False,
    min_confidence: float = 0.0,
) -> tuple[int, int]:
    """Export bookmarks as JSON Lines (one JSON object per line)."""
    out_path = Path(out_path)
    include_categories = {c.strip() for c in (include_categories or set()) if c.strip()}
    exclude_categories = {c.strip() for c in (exclude_categories or set()) if c.strip()}

    bookmarks = store.list_bookmarks()
    exported = 0
    skipped = 0

    with out_path.open("w", encoding="utf-8") as f:
        for row in bookmarks:
            bookmark_id = int(row["id"])

            if row["is_deleted"]:
                skipped += 1
                continue

            classifs = store.get_bookmark_classifications(bookmark_id)
            primary_cat = next((c["category_slug"] for c in classifs if c["is_primary"]), "misc")

            if include_categories and primary_cat not in include_categories:
                skipped += 1
                continue
            if exclude_categories and primary_cat in exclude_categories:
                skipped += 1
                continue
            if exclude_review and row["needs_review"]:
                skipped += 1
                continue
            if float(row.get("confidence", 0)) < min_confidence:
                skipped += 1
                continue

            links = store.get_bookmark_links(bookmark_id)
            entities = store.get_bookmark_entities(bookmark_id)
            tags = store.get_bookmark_tags(bookmark_id)

            record = {
                "status_id": str(row["status_id"]),
                "status_url": row["status_url"],
                "author_handle": row["author_handle"],
                "author_name": row["author_name"],
                "tweet_text": row["tweet_text"],
                "raw_text": row["raw_text"],
                "summary": row["summary"],
                "primary_category": primary_cat,
                "categories": [c["category_slug"] for c in classifs],
                "confidence": float(row.get("confidence", 0)) if "confidence" in row else None,
                "review_state": row["review_state"],
                "entities": [e["name"] for e in entities],
                "links": [link["url"] for link in links],
                "tags": tags,
                "captured_at": row["captured_at"],
                "created_at": row["created_at"],
            }
            # Remove None values
            record = {k: v for k, v in record.items() if v is not None}

            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            exported += 1

    return exported, skipped
