from __future__ import annotations

import json
from pathlib import Path

from ..util import ensure_dir, slugify


def export_obsidian(
    store,
    vault: Path,
    include_categories: set[str] | None = None,
    exclude_categories: set[str] | None = None,
    exclude_review: bool = False,
    min_confidence: float = 0.0,
    include_projects: bool = True,
    include_clusters: bool = False,
) -> tuple[int, int]:
    """Export bookmarks as Obsidian Markdown notes."""
    vault = Path(vault)
    notes_dir = ensure_dir(vault / "Bookmarks")
    topics_dir = ensure_dir(vault / "Topics")
    entities_dir = ensure_dir(vault / "Entities")
    projects_dir = ensure_dir(vault / "Projects") if include_projects else None
    clusters_dir = ensure_dir(vault / "Clusters") if include_clusters else None

    bookmarks = store.list_bookmarks()
    include_categories = {c.strip() for c in (include_categories or set()) if c.strip()}
    exclude_categories = {c.strip() for c in (exclude_categories or set()) if c.strip()}

    exported = 0
    skipped = 0
    by_category: dict[str, list[tuple[str, str]]] = {}
    by_entity: dict[str, list[tuple[str, str]]] = {}

    for row in bookmarks:
        bookmark_id = int(row["id"])

        # Apply filters
        if row["is_deleted"]:
            skipped += 1
            continue

        classifs = store.get_bookmark_classifications(bookmark_id)
        primary_cat = None
        all_cats = []
        for c in classifs:
            if c["is_primary"]:
                primary_cat = c["category_slug"]
            all_cats.append(c["category_slug"])

        if include_categories and primary_cat not in include_categories:
            skipped += 1
            continue
        if exclude_categories and primary_cat in exclude_categories:
            skipped += 1
            continue
        if exclude_review and row["needs_review"]:
            skipped += 1
            continue

        # Render note
        filename = _note_filename(row)
        note_path = notes_dir / filename
        note_path.write_text(_render_note(store, row, classifs), encoding="utf-8")
        exported += 1

        # Track for index files
        label = primary_cat or "misc"
        summary = row["summary"] or row["tweet_text"] or row["status_id"]
        by_category.setdefault(label, []).append((summary[:100], f"Bookmarks/{filename[:-3]}"))

        # Entities
        entities = store.get_bookmark_entities(bookmark_id)
        for e in entities:
            entity_name = e["name"]
            by_entity.setdefault(entity_name, []).append((summary[:100], f"Bookmarks/{filename[:-3]}"))

    # Write category index files
    for cat_slug, items in by_category.items():
        cat_row = store.get_category(cat_slug)
        label = cat_row["label"] if cat_row else cat_slug.replace("-", " ").title()
        lines = [f"# {label}", "", f"{len(items)} bookmarks.", ""]
        for title, link in sorted(items):
            lines.append(f"- [[{link}|{title}]]")
        (topics_dir / f"{slugify(label)}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Write entity index files
    for entity_name, items in by_entity.items():
        lines = [f"# {entity_name}", "", f"Appears in {len(items)} bookmarks.", ""]
        for title, link in sorted(items):
            lines.append(f"- [[{link}|{title}]]")
        (entities_dir / f"{slugify(entity_name)}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Write project notes
    if include_projects:
        projects = store.get_projects()
        for project in projects:
            sources = store.get_project_sources(int(project["id"]))
            project_path = projects_dir / f"{project['slug']}.md"
            project_path.write_text(_render_project(project, sources), encoding="utf-8")

    # Write cluster notes
    if include_clusters:
        clusters = store.get_clusters()
        for cluster in clusters:
            members = store.get_cluster_members(int(cluster["id"]))
            cluster_path = clusters_dir / f"{cluster['slug']}.md"
            cluster_path.write_text(_render_cluster(cluster, members), encoding="utf-8")

    return exported, skipped


def _note_filename(row) -> str:
    base = row["summary"] or row["tweet_text"] or row["status_id"]
    return f"{row['status_id']}-{slugify(base)}.md"


def _render_note(store, row, classifs) -> str:
    bookmark_id = int(row["id"])
    links = store.get_bookmark_links(bookmark_id)
    entities = store.get_bookmark_entities(bookmark_id)
    tags = store.get_bookmark_tags(bookmark_id)

    frontmatter = {
        "type": "tweet-bookmark",
        "status_id": str(row["status_id"]),
        "source": row["status_url"],
        "author": row["author_handle"] or row["author_name"],
        "categories": [c["category_slug"] for c in classifs],
        "confidence": float(row.get("confidence", 0)) if "confidence" in row else None,
        "review_state": row["review_state"],
        "exportable": bool(row["is_exportable"]),
        "captured": row["captured_at"],
    }
    # Remove None values
    frontmatter = {k: v for k, v in frontmatter.items() if v is not None}

    lines = ["---"]
    for key, value in frontmatter.items():
        lines.append(f"{key}: {json.dumps(value)}")
    lines.extend(["---", "", f"# {row['summary'] or row['status_id']}", ""])

    cat_links = []
    for c in classifs:
        slug = c["category_slug"]
        label = slug.replace("-", " ").title()
        cat_links.append(f"[[Topics/{label}]]")
    cat_str = ", ".join(cat_links)

    lines.extend([
        f"Source: [{row['status_url']}]({row['status_url']})",
        f"Author: {row['author_name']} @{row['author_handle']}".strip(),
        f"Categories: {cat_str}",
        "",
        "## Summary",
        row["summary"] or "",
        "",
        "## Why It Matters",
        row["why_it_matters"] or "",
        "",
        "## Tweet Text",
        row["tweet_text"] or row["raw_text"] or "",
    ])

    if links:
        lines.extend(["", "## Links"])
        for link in links:
            lines.append(f"- [{link['url']}]({link['url']})")

    if entities:
        lines.extend(["", "## Entities"])
        for e in entities:
            lines.append(f"- {e['name']} ({e['type']})")

    if tags:
        lines.extend(["", "## Tags"])
        lines.append(", ".join(f"#{t}" for t in tags))

    if row["review_note"]:
        lines.extend(["", "## Review Note", row["review_note"]])

    return "\n".join(lines).rstrip() + "\n"


def _render_project(project, sources) -> str:
    lines = [
        f"# {project['title']}",
        "",
        f"**One-liner:** {project['one_liner']}",
        f"**Status:** {project['status']}",
        f"**Confidence:** {project['confidence']:.0%}",
        "",
    ]
    if project.get("problem"):
        lines.extend(["## Problem", project["problem"], ""])
    if project.get("audience"):
        lines.extend(["## Audience", project["audience"], ""])
    if project.get("why_now"):
        lines.extend(["## Why Now", project["why_now"], ""])
    if project.get("implementation_notes"):
        lines.extend(["## Implementation Notes", project["implementation_notes"], ""])
    if sources:
        lines.extend(["## Evidence", ""])
        for s in sources:
            text = s["tweet_text"] or s["raw_text"] or ""
            lines.append(f"- [[Bookmarks/{s['status_id']}-{slugify(text[:50])}]]")
    return "\n".join(lines) + "\n"


def _render_cluster(cluster, members) -> str:
    lines = [
        f"# {cluster['label']}",
        "",
        f"**Summary:** {cluster.get('summary') or 'No summary'}",
        f"**Method:** {cluster['method']}",
        "",
        f"**Members:** {len(members)}",
        "",
    ]
    for m in members[:20]:
        text = m["tweet_text"] or m["raw_text"] or ""
        lines.append(f"- [[Bookmarks/{m['status_id']}-{slugify(text[:50])}]]")
    return "\n".join(lines) + "\n"
