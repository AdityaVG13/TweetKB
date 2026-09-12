from __future__ import annotations

from conftest import add_bookmark

from tweetkb.clusters import generate_clusters


def test_generate_clusters_groups_same_primary_category(store):
    for status_id, text in (
        ("1", "browser agent mcp tool use"),
        ("2", "autonomous agent loop with tool use"),
        ("3", "multi-agent browser automation"),
    ):
        bookmark_id = add_bookmark(store, status_id, text)
        store.set_classifications(
            bookmark_id,
            [{"slug": "ai-agents", "confidence": 0.9, "method": "keyword"}],
            "ai-agents",
            0.9,
        )

    result = generate_clusters(store, min_size=3, min_confidence=0.4)

    assert result["clusters_created"] >= 1
    assert result["bookmarks_clustered"] == 3
    members = store.conn.execute("SELECT count(*) AS n FROM cluster_members").fetchone()
    assert int(members["n"]) == 3


def test_generate_clusters_skips_low_confidence(store):
    bookmark_id = add_bookmark(store, "1", "hello")
    store.set_classifications(
        bookmark_id,
        [{"slug": "misc", "confidence": 0.1, "method": "keyword"}],
        "misc",
        0.1,
    )

    result = generate_clusters(store, min_size=1, min_confidence=0.4)

    assert result["bookmarks_clustered"] == 0
