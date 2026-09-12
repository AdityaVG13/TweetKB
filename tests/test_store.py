from __future__ import annotations

from pathlib import Path

import pytest
from conftest import add_bookmark

from tweetkb.db import Store


def test_opening_a_missing_database_hard_fails_without_creating_the_file(tmp_path: Path):
    path = tmp_path / "missing.sqlite3"

    with pytest.raises(FileNotFoundError, match="tweetkb init"):
        Store(path)

    assert not path.exists()


def test_init_creates_schema_version_4_or_newer(store):
    assert store.schema_version() >= 4


def test_store_uses_wal(store):
    mode = store.conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert str(mode).lower() == "wal"


def test_upsert_replaces_same_status_id_and_keeps_one_row(store):
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
    assert [link["url"] for link in store.get_bookmark_links(first)] == [
        "https://example.com/a",
        "https://example.com/b",
    ]


def test_identical_upsert_is_reported_unchanged(store):
    first = store.upsert_bookmark_with_status({"status_url": "https://x.com/a/status/1", "tweet_text": "hello"})
    second = store.upsert_bookmark_with_status({"status_url": "https://x.com/a/status/1", "tweet_text": "hello"})

    assert first is not None
    assert second == (first[0], False)


def test_supplied_captured_at_is_stored(store):
    store.upsert_bookmark_with_status(
        {
            "status_url": "https://x.com/a/status/1",
            "tweet_text": "first",
            "captured_at": "2026-05-08T10:00:00+00:00",
        }
    )

    row = store.get_bookmark_by_status("1")
    assert row["captured_at"] == "2026-05-08T10:00:00+00:00"


def test_stats_count_the_inserted_author(store):
    add_bookmark(store, "1", "hello", handle="alice")
    stats = store.stats()

    assert stats["total"] == 1
    assert stats["needs_review"] == 1
    assert stats["top_authors"][0]["handle"] == "alice"
    assert stats["top_authors"][0]["count"] == 1


def test_content_enrichment_roundtrip(store):
    bookmark_id = add_bookmark(store, "1", "hello", handle="alice")
    store.set_content_enrichment(
        bookmark_id,
        source_url="https://x.com/alice/status/1",
        source_type="x-status",
        title="Full post",
        content_text="longer captured body",
    )
    rows = store.get_content_enrichments(bookmark_id)

    assert len(rows) == 1
    assert rows[0]["content_text"] == "longer captured body"
    assert rows[0]["source_type"] == "x-status"
