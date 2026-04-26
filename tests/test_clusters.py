from pathlib import Path
from tweetkb.clusters import generate_clusters
from tweetkb.db import Store


def test_generate_clusters_empty_db(tmp_path: Path):
    """generate_clusters handles empty database."""
    store = Store(tmp_path / "db.sqlite3")
    store.init()
    result = generate_clusters(store)
    # Returns stats dict when no clusters created
    assert "clusters_created" in result
    assert result["clusters_created"] == 0
    store.close()


def test_generate_clusters_with_bookmarks(tmp_path: Path):
    """generate_clusters returns stats including bookmarks_clustered."""
    store = Store(tmp_path / "db.sqlite3")
    store.init()
    id1 = store.upsert_bookmark({"status_url": "https://x.com/user/status/1", "tweet_text": "AI agent tool"})
    id2 = store.upsert_bookmark({"status_url": "https://x.com/user/status/2", "tweet_text": "AI agent workflow"})
    store.set_classifications(id1, [{"slug": "ai-agents", "confidence": 0.9, "method": "test"}], "ai-agents", 0.9)
    store.set_classifications(id2, [{"slug": "ai-agents", "confidence": 0.9, "method": "test"}], "ai-agents", 0.9)
    result = generate_clusters(store)
    assert "clusters_created" in result
    assert "bookmarks_clustered" in result
    assert result["bookmarks_clustered"] == 2
    store.close()
