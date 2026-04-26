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
    store.upsert_bookmark({"status_url": "https://x.com/a/status/1", "tweet_text": "hello"})
    stats = store.stats()
    assert stats["total"] == 1
    assert stats["needs_review"] == 1
    store.close()
