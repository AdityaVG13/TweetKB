from pathlib import Path
from tweetkb.migrations import SCHEMA_VERSION, migrate


def test_schema_version():
    """Schema version is set correctly."""
    assert SCHEMA_VERSION == 3


def test_migrate_creates_tables(tmp_path: Path):
    """Migration creates all required tables."""
    import sqlite3
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    migrate(conn)
    conn.close()
    # Reconnect and verify
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    # Check bookmarks table exists
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='bookmarks'").fetchall()
    assert len(rows) == 1
    conn.close()


def test_migrate_legacy_v1_preserves_bookmarks(tmp_path: Path):
    """Legacy v1 DBs are rebuilt into v2 without losing bookmarks."""
    import sqlite3

    from tweetkb.migrations import SCHEMA_V1

    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_V1)
    conn.execute(
        """INSERT INTO bookmarks
           (status_id, status_url, author_name, author_handle, tweet_text, raw_text,
            category, confidence, summary, why_it_matters, content_hash)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            "123",
            "https://x.com/alice/status/123",
            "Alice",
            "alice",
            "Useful agent workflow",
            "Useful agent workflow",
            "ai-agents",
            0.9,
            "Agent workflow",
            "Reusable pattern",
            "hash-123",
        ),
    )
    conn.execute("INSERT INTO tags(name) VALUES (?)", ("agents",))
    conn.execute("INSERT INTO bookmark_tags(bookmark_id, tag_id) VALUES (?, ?)", (1, 1))
    conn.commit()

    migrate(conn)

    cols = [r["name"] for r in conn.execute("PRAGMA table_info(bookmarks)").fetchall()]
    assert "review_state" in cols
    assert "is_deleted" in cols
    assert "category" not in cols
    row = conn.execute("SELECT * FROM bookmarks WHERE status_id = '123'").fetchone()
    assert row["tweet_text"] == "Useful agent workflow"
    assert row["review_state"] == "new"
    classification = conn.execute("SELECT category_slug FROM classifications WHERE bookmark_id = ?", (row["id"],)).fetchone()
    assert classification["category_slug"] == "ai-agents"
    tag = conn.execute(
        """SELECT t.name FROM tags t
           JOIN bookmark_tags bt ON bt.tag_id = t.id
           WHERE bt.bookmark_id = ?""",
        (row["id"],),
    ).fetchone()
    assert tag["name"] == "agents"
    conn.close()


def test_repair_v2_adds_review_state(tmp_path: Path):
    """Partially migrated v2 DBs get missing review columns added."""
    import sqlite3

    db_path = tmp_path / "partial.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE bookmarks (
          id INTEGER PRIMARY KEY,
          status_id TEXT UNIQUE NOT NULL,
          status_url TEXT NOT NULL,
          author_name TEXT,
          author_handle TEXT,
          tweet_text TEXT NOT NULL DEFAULT '',
          raw_text TEXT NOT NULL DEFAULT '',
          created_at TEXT,
          captured_at TEXT NOT NULL DEFAULT (datetime('now')),
          updated_at TEXT NOT NULL DEFAULT (datetime('now')),
          content_hash TEXT NOT NULL
        );
        CREATE TABLE schema_migrations (
          version INTEGER PRIMARY KEY,
          name TEXT NOT NULL,
          applied_at TEXT NOT NULL
        );
        INSERT INTO schema_migrations(version, name, applied_at)
        VALUES (2, 'partial v2', '2026-04-28T00:00:00+00:00');
        """
    )

    migrate(conn)

    cols = [r["name"] for r in conn.execute("PRAGMA table_info(bookmarks)").fetchall()]
    assert "review_state" in cols
    assert "processing_events" in [
        r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    ]
    conn.close()


def test_migrate_adds_content_enrichments(tmp_path: Path):
    """Migration creates full-content enrichment storage."""
    import sqlite3

    db_path = tmp_path / "content.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    migrate(conn)
    tables = [r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    assert "content_enrichments" in tables
    version = conn.execute("SELECT max(version) AS v FROM schema_migrations").fetchone()["v"]
    assert version == 3
    conn.close()
