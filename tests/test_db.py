from pathlib import Path

from tweetkb.db import Store


def test_upsert_deduplicates_status_id(tmp_path: Path):
    store = Store(tmp_path / "db.sqlite3")
    store.init()
    first = store.upsert_bookmark(
        {
            "status_url": "https://x.com/a/status/1",
            "tweet_text": "hello",
            "links": ["https://example.com/a"],
        }
    )
    second = store.upsert_bookmark(
        {
            "status_url": "https://x.com/a/status/1",
            "tweet_text": "hello again",
            "links": ["https://example.com/a", "https://example.com/b"],
        }
    )
    rows = store.list_bookmarks()
    assert first == second
    assert len(rows) == 1
    assert rows[0]["tweet_text"] == "hello again"
    assert [link["url"] for link in store.get_bookmark_links(first)] == ["https://example.com/a", "https://example.com/b"]
    store.close()


def test_upsert_reports_unchanged_existing_rows(tmp_path: Path):
    store = Store(tmp_path / "db.sqlite3")
    store.init()
    first = store.upsert_bookmark_with_status({"status_url": "https://x.com/a/status/1", "tweet_text": "hello"})
    second = store.upsert_bookmark_with_status({"status_url": "https://x.com/a/status/1", "tweet_text": "hello"})
    assert first is not None
    assert second == (first[0], False)
    store.close()


def test_upsert_uses_supplied_capture_order_timestamp(tmp_path: Path):
    store = Store(tmp_path / "db.sqlite3")
    store.init()
    store.upsert_bookmark_with_status(
        {
            "status_url": "https://x.com/a/status/1",
            "tweet_text": "first",
            "captured_at": "2026-05-08T10:00:00+00:00",
        }
    )

    row = store.get_bookmark_by_status("1")
    assert row["captured_at"] == "2026-05-08T10:00:00+00:00"
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
        "https://x.com/a/status/1#conversation",
        "thread and reply body",
        source_type="x-conversation",
        title="Thread context",
    )
    store.set_content_enrichment(
        bookmark_id,
        "https://example.com/story",
        "linked story body",
        source_type="linked-page",
        title="Story",
    )
    rows = store.get_content_enrichments(bookmark_id)
    assert [r["source_type"] for r in rows] == ["x-status", "x-conversation", "linked-page"]
    pending = store.list_bookmarks_for_enrichment()
    assert pending == []
    store.close()


def test_list_bookmarks_for_enrichment_can_target_missing_source_type(tmp_path: Path):
    store = Store(tmp_path / "db.sqlite3")
    store.init()
    bookmark_id = store.upsert_bookmark(
        {
            "status_url": "https://x.com/a/status/1",
            "author_handle": "a",
            "tweet_text": "preview with image",
        }
    )
    assert bookmark_id is not None
    store.set_content_enrichment(
        bookmark_id,
        "https://x.com/a/status/1",
        "full tweet text",
        source_type="x-status",
    )
    store.set_classifications(
        bookmark_id,
        [{"slug": "vision", "confidence": 0.9, "method": "test", "rationale": ""}],
        "vision",
        0.9,
    )

    pending_text = store.list_bookmarks_for_enrichment()
    pending_media = store.list_bookmarks_for_enrichment(missing_source_type="image-analysis")
    pending_media_category = store.list_bookmarks_for_enrichment(
        category="vision",
        missing_source_type="image-analysis",
    )

    assert pending_text == []
    assert [row["id"] for row in pending_media] == [bookmark_id]
    assert [row["id"] for row in pending_media_category] == [bookmark_id]
    store.close()
