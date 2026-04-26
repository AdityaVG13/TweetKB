from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from .util import slugify


def build_graph(store) -> dict:
    """Build a graph structure from all bookmark data."""
    nodes = []
    edges = []
    seen_nodes: set = set()
    seen_edges: set = set()

    def add_node(node_type: str, node_id: str, attrs: dict) -> None:
        key = f"{node_type}:{node_id}"
        if key not in seen_nodes:
            seen_nodes.add(key)
            nodes.append({"type": node_type, "id": node_id, **attrs})

    def add_edge(
        from_type: str, from_id: str,
        to_type: str, to_id: str,
        rel: str,
        attrs: dict | None = None,
    ) -> None:
        key = f"{from_type}:{from_id}->{rel}->{to_type}:{to_id}"
        if key not in seen_edges:
            seen_edges.add(key)
            edges.append({
                "from": {"type": from_type, "id": from_id},
                "to": {"type": to_type, "id": to_id},
                "relation": rel,
                **(attrs or {}),
            })

    # Bookmark nodes
    bookmarks = store.list_bookmarks()
    for row in bookmarks:
        bookmark_id = str(row["id"])
        add_node("bookmark", bookmark_id, {
            "label": (row["summary"] or row["tweet_text"] or "")[:80],
            "status_id": row["status_id"],
            "author": row["author_handle"],
            "review_state": row["review_state"],
            "needs_review": bool(row["needs_review"]),
        })

        # bookmark -> category
        classifs = store.get_bookmark_classifications(int(bookmark_id))
        for c in classifs:
            if c["is_primary"]:
                add_edge("bookmark", bookmark_id, "category", c["category_slug"], "categorized_as", {
                    "confidence": c["confidence"],
                })

        # bookmark -> entity
        entities = store.get_bookmark_entities(int(bookmark_id))
        for e in entities:
            add_node("entity", str(e["id"]), {
                "name": e["name"],
                "type": e["type"],
            })
            add_edge("bookmark", bookmark_id, "entity", str(e["id"]), "mentions", {
                "salience": e["salience"],
            })

        # bookmark -> author
        if row["author_handle"]:
            add_node("author", row["author_handle"], {
                "handle": row["author_handle"],
                "name": row["author_name"],
            })
            add_edge("bookmark", bookmark_id, "author", row["author_handle"], "authored_by")

        # bookmark -> domain
        links = store.get_bookmark_links(int(bookmark_id))
        for link in links:
            domain = link["domain"] or ""
            if domain:
                add_node("domain", domain, {"domain": domain})
                add_edge("bookmark", bookmark_id, "domain", domain, "links_to")
            add_node("link", str(link["id"]), {
                "url": link["url"],
                "domain": link["domain"],
            })
            add_edge("bookmark", bookmark_id, "link", str(link["id"]), "references")

    # Category nodes
    categories = store.get_categories()
    for cat in categories:
        add_node("category", cat["slug"], {
            "label": cat["label"],
            "description": cat.get("description") or "",
        })

    # Cluster nodes
    clusters = store.get_clusters()
    for cluster in clusters:
        cluster_id = str(cluster["id"])
        add_node("cluster", cluster_id, {
            "label": cluster["label"],
            "slug": cluster["slug"],
            "summary": cluster.get("summary") or "",
        })

        # cluster -> bookmark
        members = store.get_cluster_members(int(cluster_id))
        for member in members:
            add_edge("cluster", cluster_id, "bookmark", str(member["id"]), "contains", {
                "score": member["score"],
            })

    # Project nodes
    projects = store.get_projects()
    for project in projects:
        project_id = str(project["id"])
        add_node("project", project_id, {
            "title": project["title"],
            "slug": project["slug"],
            "one_liner": project["one_liner"],
            "status": project["status"],
            "confidence": project["confidence"],
        })

        # project -> cluster
        if project.get("source_cluster_id"):
            add_edge("project", project_id, "cluster", str(project["source_cluster_id"]), "derived_from")

        # project -> bookmark
        sources = store.get_project_sources(int(project_id))
        for source in sources:
            add_edge("project", project_id, "bookmark", str(source["id"]), "uses_as_evidence", {
                "role": source["role"],
            })

    return {"nodes": nodes, "edges": edges}


def export_graph_json(store, out_path: Path) -> None:
    """Export full graph as JSON."""
    graph = build_graph(store)
    out_path.write_text(json.dumps(graph, indent=2, ensure_ascii=False))


def get_graph_stats(graph: dict) -> dict:
    """Compute stats from a graph dict."""
    nodes_by_type = defaultdict(int)
    edges_by_rel = defaultdict(int)
    for node in graph.get("nodes", []):
        nodes_by_type[node.get("type", "unknown")] += 1
    for edge in graph.get("edges", []):
        edges_by_rel[edge.get("relation", "unknown")] += 1
    return {
        "node_count": len(graph.get("nodes", [])),
        "edge_count": len(graph.get("edges", [])),
        "nodes_by_type": dict(nodes_by_type),
        "edges_by_relation": dict(edges_by_rel),
    }
