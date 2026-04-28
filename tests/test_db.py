from pathlib import Path

from tweetkb.db import Store


def test_upsert_deduplicates_status_id(tmp_path: Path):
    store = Store(tmp_path / "db.sqlite3")
    store.init()
    first = store.upsert_bookmark({"status_url": "https://x.com/a/status/1", "tweet_text": "hello"})
    second = store.upsert_bookmark({"status_url": "https://x.com/a/status/1", "tweet_text": "hello again"})
    rows = store.list_bookmarks()
    assert first == second
    assert len(rows) == 1
    assert rows[0]["tweet_text"] == "hello again"
    store.close()


def test_upsert_reports_unchanged_existing_rows(tmp_path: Path):
    store = Store(tmp_path / "db.sqlite3")
    store.init()
    first = store.upsert_bookmark_with_status({"status_url": "https://x.com/a/status/1", "tweet_text": "hello"})
    second = store.upsert_bookmark_with_status({"status_url": "https://x.com/a/status/1", "tweet_text": "hello"})
    assert first is not None
    assert second == (first[0], False)
    store.close()


def test_stats(tmp_path: Path):
    store = Store(tmp_path / "db.sqlite3")
    store.init()
    store.upsert_bookmark(
        {
            "status_url": "https://x.com/a/status/1",
            "author_handle": "a",
            "author_name": "Alice",
            "tweet_text": "hello",
        }
    )
    stats = store.stats()
    assert stats["total"] == 1
    assert stats["needs_review"] == 1
    assert stats["top_authors"][0]["handle"] == "a"
    assert stats["top_authors"][0]["count"] == 1
    store.close()


def test_content_enrichment_roundtrip(tmp_path: Path):
    store = Store(tmp_path / "db.sqlite3")
    store.init()
    bookmark_id = store.upsert_bookmark(
        {
            "status_url": "https://x.com/a/status/1",
            "author_handle": "a",
            "tweet_text": "preview",
        }
    )
    assert bookmark_id is not None
    saved = store.set_content_enrichment(
        bookmark_id,
        "https://x.com/a/status/1",
        "full tweet and article body",
        source_type="x-status",
        title="Full status",
    )
    assert saved is True
    row = store.get_content_enrichment(bookmark_id)
    assert row is not None
    assert row["content_text"] == "full tweet and article body"
    store.set_content_enrichment(
        bookmark_id,
        "https://example.com/story",
        "linked story body",
        source_type="linked-page",
        title="Story",
    )
    rows = store.get_content_enrichments(bookmark_id)
    assert [r["source_type"] for r in rows] == ["x-status", "linked-page"]
    pending = store.list_bookmarks_for_enrichment()
    assert pending == []
    store.close()
