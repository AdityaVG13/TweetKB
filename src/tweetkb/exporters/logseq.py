from __future__ import annotations

import json
from pathlib import Path

from ..util import ensure_dir, slugify


def export_logseq(
    store,
    vault: Path,
    include_categories: set[str] | None = None,
    exclude_categories: set[str] | None = None,
    exclude_review: bool = False,
    min_confidence: float = 0.0,
) -> tuple[int, int]:
    """Export bookmarks as Logseq-compatible Markdown pages."""
    vault = Path(vault)
    pages_dir = ensure_dir(vault / "pages")

    bookmarks = store.list_bookmarks()
    include_categories = {c.strip() for c in (include_categories or set()) if c.strip()}
    exclude_categories = {c.strip() for c in (exclude_categories or set()) if c.strip()}

    exported = 0
    skipped = 0

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

        filename = f"{row['status_id']}-{slugify(row['summary'] or row['tweet_text'][:50])}.md"
        page_path = pages_dir / filename
        page_path.write_text(_render_page(store, row, classifs), encoding="utf-8")
        exported += 1

    return exported, skipped


def _render_page(store, row, classifs) -> str:
    bookmark_id = int(row["id"])
    links = store.get_bookmark_links(bookmark_id)
    entities = store.get_bookmark_entities(bookmark_id)
    tags = store.get_bookmark_tags(bookmark_id)
    primary_cat = next((c["category_slug"] for c in classifs if c["is_primary"]), "misc")
    cat_labels = {
        "ai-agents": "AI Agents",
        "coding": "Coding",
        "models": "Models",
        "tools": "Tools",
        "papers": "Papers",
        "misc": "Misc",
    }
    cat_str = ", ".join(f"[[{cat_labels.get(c['category_slug'], c['category_slug'])}]]" for c in classifs)

    lines = [
        f"- type:: tweet-bookmark",
        f"- status-id:: {row['status_id']}",
        f"- source:: {row['status_url']}",
        f"- author:: [[{row['author_handle'] or row['author_name']}]]",
        f"- categories:: {cat_str}",
        f"- confidence:: {float(row.get('confidence', 0)):.2f}" if 'confidence' in row else "",
        f"- review-state:: {row['review_state']}",
        f"- captured:: {row['captured_at']}",
        "",
        f"# {row['summary'] or row['status_id']}",
        "",
    ]

    if row["summary"]:
        lines.extend(["## Summary", row["summary"], ""])

    if row["tweet_text"] or row["raw_text"]:
        lines.extend(["## Tweet", f"> {(row['tweet_text'] or row['raw_text'])}", ""])

    if row["why_it_matters"]:
        lines.extend(["## Why It Matters", row["why_it_matters"], ""])

    if links:
        lines.extend(["## Links", ""])
        for link in links:
            lines.append(f"- {link['url']}")
        lines.append("")

    if entities:
        lines.extend(["## Entities", ""])
        for e in entities:
            lines.append(f"- {e['name']} ({e['type']})")
        lines.append("")

    if tags:
        lines.append(f"## Tags")
        lines.append(", ".join(f"#{t}" for t in tags))
        lines.append("")

    if row["review_note"]:
        lines.extend(["## Review Note", row["review_note"], ""])

    return "\n".join(lines).rstrip() + "\n"
