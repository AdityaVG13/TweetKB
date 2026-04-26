from __future__ import annotations

import json
from pathlib import Path

from ..util import ensure_dir, slugify


def export_markdown(
    store,
    out_dir: Path,
    include_categories: set[str] | None = None,
    exclude_categories: set[str] | None = None,
    exclude_review: bool = False,
    min_confidence: float = 0.0,
) -> tuple[int, int]:
    """Export bookmarks as generic Markdown (no Obsidian/Logseq specific syntax)."""
    out_dir = Path(out_dir)
    bookmarks_dir = ensure_dir(out_dir / "bookmarks")
    topics_dir = ensure_dir(out_dir / "topics")

    bookmarks = store.list_bookmarks()
    include_categories = {c.strip() for c in (include_categories or set()) if c.strip()}
    exclude_categories = {c.strip() for c in (exclude_categories or set()) if c.strip()}

    exported = 0
    skipped = 0
    by_category: dict[str, list[tuple[str, str]]] = {}

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
        file_path = bookmarks_dir / filename
        file_path.write_text(_render_md(store, row, classifs), encoding="utf-8")
        exported += 1

        label = primary_cat or "misc"
        summary = row["summary"] or row["tweet_text"] or row["status_id"]
        by_category.setdefault(label, []).append((summary[:100], f"bookmarks/{filename[:-3]}"))

    # Write topic indexes
    for cat_slug, items in by_category.items():
        lines = [f"# {cat_slug.replace('-', ' ').title()}", "", f"{len(items)} bookmarks.", ""]
        for title, link in sorted(items):
            lines.append(f"- [{title}]({link}.md)")
        (topics_dir / f"{cat_slug}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Write index
    index_path = out_dir / "index.md"
    index_lines = ["# Bookmark Export", "", f"Total: {exported} bookmarks", ""]
    index_lines.append("## Topics")
    for cat_slug in sorted(by_category.keys()):
        count = len(by_category[cat_slug])
        index_lines.append(f"- [{cat_slug}](topics/{cat_slug}.md) ({count})")
    index_path.write_text("\n".join(index_lines) + "\n", encoding="utf-8")

    return exported, skipped


def _render_md(store, row, classifs) -> str:
    bookmark_id = int(row["id"])
    links = store.get_bookmark_links(bookmark_id)
    entities = store.get_bookmark_entities(bookmark_id)
    tags = store.get_bookmark_tags(bookmark_id)

    frontmatter = {
        "status_id": str(row["status_id"]),
        "url": row["status_url"],
        "author": row["author_handle"] or row["author_name"],
        "categories": [c["category_slug"] for c in classifs],
        "review_state": row["review_state"],
        "captured": row["captured_at"],
    }

    lines = ["---"]
    for key, value in frontmatter.items():
        lines.append(f"{key}: {json.dumps(value)}")
    lines.extend(["---", "", f"# {row['summary'] or row['status_id']}", ""])

    if row["summary"]:
        lines.extend(["## Summary", row["summary"], ""])

    lines.extend(["## Tweet", row["tweet_text"] or row["raw_text"] or "", ""])

    if row["why_it_matters"]:
        lines.extend(["## Why It Matters", row["why_it_matters"], ""])

    if links:
        lines.extend(["## Links"] + [f"- {link['url']}" for link in links] + [""])

    if entities:
        lines.extend(["## Entities"] + [f"- {e['name']} ({e['type']})" for e in entities] + [""])

    if tags:
        lines.extend(["## Tags", ", ".join(f"#{t}" for t in tags), ""])

    return "\n".join(lines).rstrip() + "\n"
