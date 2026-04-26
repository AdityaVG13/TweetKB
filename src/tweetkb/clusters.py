from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from .util import slugify


def generate_clusters(store, min_size: int = 3, min_confidence: float = 0.4) -> dict[str, Any]:
    """Generate topic clusters from classified bookmarks."""
    now = datetime.now(timezone.utc).isoformat()

    # Get all classified bookmarks grouped by primary category
    bookmarks_by_cat: dict[str, list[dict]] = defaultdict(list)

    rows = store.list_bookmarks()
    for row in rows:
        classifications = store.get_bookmark_classifications(int(row["id"]))
        if not classifications:
            continue
        primary = next((c for c in classifications if c["is_primary"]), classifications[0])
        if float(primary["confidence"]) < min_confidence:
            continue
        bookmarks_by_cat[primary["category_slug"]].append({
            "id": int(row["id"]),
            "category": primary["category_slug"],
            "confidence": float(primary["confidence"]),
            "text": (row["tweet_text"] or "")[:300],
        })

    # Generate clusters
    clusters_created = 0
    bookmarks_clustered = 0
    cluster_map: dict[int, int] = {}  # bookmark_id -> cluster_id

    # Cluster by category + entity overlap
    for category, bookmarks in bookmarks_by_cat.items():
        if len(bookmarks) < min_size:
            # Small categories: single cluster if has items
            if bookmarks:
                label = category.replace("-", " ").title()
                slug = slugify(f"cluster-{category}-{label}")
                cluster_id = _upsert_cluster(store, slug, label, f"Auto-generated {category} cluster", "heuristic", now)
                for bm in bookmarks:
                    _add_cluster_member(store, cluster_id, bm["id"], bm["confidence"])
                    cluster_map[bm["id"]] = cluster_id
                clusters_created += 1
                bookmarks_clustered += len(bookmarks)
            continue

        # Large categories: split by entity/keyword similarity
        sub_clusters = _split_by_entities(bookmarks, store)
        for sub_label, sub_bookmarks in sub_clusters.items():
            if len(sub_bookmarks) < min_size:
                continue
            full_label = f"{category.replace('-', ' ').title()}: {sub_label}"
            slug = slugify(f"cluster-{category}-{sub_label}")
            cluster_id = _upsert_cluster(
                store, slug, full_label,
                f"Auto-generated cluster for {category} / {sub_label}",
                "heuristic", now
            )
            for bm in sub_bookmarks:
                _add_cluster_member(store, cluster_id, bm["id"], bm["confidence"])
                cluster_map[bm["id"]] = cluster_id
            clusters_created += 1
            bookmarks_clustered += len(sub_bookmarks)

    return {
        "clusters_created": clusters_created,
        "bookmarks_clustered": bookmarks_clustered,
    }


def _split_by_entities(bookmarks: list[dict], store) -> dict[str, list[dict]]:
    """Split bookmarks into sub-clusters based on entity overlap."""
    # Get entities for each bookmark
    bookmark_entities: dict[int, set[str]] = {}
    entity_bookmarks: dict[str, set[int]] = defaultdict(set)

    for bm in bookmarks:
        entities = store.get_bookmark_entities(bm["id"])
        names = {e["name"].lower() for e in entities}
        bookmark_entities[bm["id"]] = names
        for name in names:
            entity_bookmarks[name].add(bm["id"])

    if not entity_bookmarks:
        return {"General": bookmarks}

    # Find dominant entities
    sorted_entities = sorted(entity_bookmarks.items(), key=lambda x: -len(x[1]))
    top_entities = [e for e, _ in sorted_entities[:5]]

    # Group by top entity presence
    groups: dict[str, list[dict]] = defaultdict(list)
    for bm in bookmarks:
        bm_ents = bookmark_entities.get(bm["id"], set())
        matched = [e for e in top_entities if e in bm_ents]
        if matched:
            group_key = matched[0].title()
        else:
            group_key = "General"
        groups[group_key].append(bm)

    return dict(groups)


def _upsert_cluster(
    store,
    slug: str,
    label: str,
    summary: str,
    method: str,
    now: str,
) -> int:
    """Insert or update a cluster."""
    existing = store.conn.execute("SELECT id FROM clusters WHERE slug = ?", (slug,)).fetchone()
    if existing:
        store.conn.execute(
            """UPDATE clusters SET label=?, summary=?, updated_at=? WHERE id=?""",
            (label, summary, now, int(existing["id"])),
        )
        store.conn.commit()
        return int(existing["id"])

    store.conn.execute(
        """INSERT INTO clusters(slug, label, summary, method, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (slug, label, summary, method, now, now),
    )
    store.conn.commit()
    return int(store.conn.execute("SELECT last_insert_rowid()").fetchone()[0])


def _add_cluster_member(store, cluster_id: int, bookmark_id: int, score: float) -> None:
    """Add a bookmark to a cluster."""
    store.conn.execute(
        """INSERT OR REPLACE INTO cluster_members(cluster_id, bookmark_id, score)
           VALUES (?, ?, ?)""",
        (cluster_id, bookmark_id, score),
    )
    store.conn.commit()
