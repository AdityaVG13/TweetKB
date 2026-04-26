from __future__ import annotations

import json
from pathlib import Path

from .categories import CATEGORY_LABELS
from .db import Store
from .util import ensure_dir, slugify


def export_obsidian(
    store: Store,
    vault: Path,
    exclude_categories: set[str] | None = None,
    include_categories: set[str] | None = None,
    exclude_review: bool = False,
) -> int:
    vault = ensure_dir(Path(vault))
    notes_dir = ensure_dir(vault / "Bookmarks")
    index_dir = ensure_dir(vault / "Topics")
    rows = store.list_bookmarks()
    exclude_categories = {c.strip() for c in (exclude_categories or set()) if c.strip()}
    include_categories = {c.strip() for c in (include_categories or set()) if c.strip()}
    count = 0
    by_category: dict[str, list[tuple[str, str]]] = {}
    for row in rows:
        if include_categories and row["category"] not in include_categories:
            continue
        if row["category"] in exclude_categories:
            continue
        if exclude_review and row["needs_review"]:
            continue
        filename = note_filename(row)
        note_path = notes_dir / filename
        note_path.write_text(render_note(row), encoding="utf-8")
        by_category.setdefault(row["category"], []).append((row["summary"] or row["tweet_text"][:80], f"Bookmarks/{filename[:-3]}"))
        count += 1

    for category, items in by_category.items():
        label = CATEGORY_LABELS.get(category, category.replace("-", " ").title())
        body = [f"# {label}", "", f"{len(items)} bookmarks.", ""]
        for title, link in sorted(items):
            body.append(f"- [[{link}|{title[:100]}]]")
        (index_dir / f"{slugify(label)}.md").write_text("\n".join(body) + "\n", encoding="utf-8")
    return count


def parse_category_csv(value: str | None) -> set[str]:
    if not value:
        return set()
    return {part.strip() for part in value.split(",") if part.strip()}


def note_filename(row) -> str:
    base = row["summary"] or row["tweet_text"] or row["status_id"]
    return f"{row['status_id']}-{slugify(base)}.md"


def render_note(row) -> str:
    links = json.loads(row["links_json"] or "[]")
    use_cases = json.loads(row["use_cases_json"] or "[]")
    entities = json.loads(row["entities_json"] or "[]")
    frontmatter = {
        "status_id": row["status_id"],
        "status_url": row["status_url"],
        "author": row["author_handle"] or row["author_name"],
        "category": row["category"],
        "confidence": row["confidence"],
        "needs_review": bool(row["needs_review"]),
    }
    lines = ["---"]
    for key, value in frontmatter.items():
        lines.append(f"{key}: {json.dumps(value)}")
    lines.extend(["---", "", f"# {row['summary'] or row['status_id']}", ""])
    lines.extend(
        [
            f"Source: {row['status_url']}",
            f"Author: {row['author_name']} @{row['author_handle']}".strip(),
            f"Category: [[Topics/{slugify(row['category'])}|{row['category']}]]",
            "",
            "## Summary",
            row["summary"] or "",
            "",
            "## Why It Matters",
            row["why_it_matters"] or "",
            "",
            "## Tweet Text",
            row["tweet_text"] or row["raw_text"] or "",
            "",
            "## Use Cases",
        ]
    )
    lines.extend(f"- {item}" for item in use_cases)
    lines.extend(["", "## Entities"])
    lines.extend(f"- {item}" for item in entities)
    lines.extend(["", "## Links"])
    lines.extend(f"- {url}" for url in links)
    if row["review_note"]:
        lines.extend(["", "## Review Note", row["review_note"]])
    return "\n".join(lines).rstrip() + "\n"
