from pathlib import Path
from tweetkb.migrations import SCHEMA_VERSION, migrate


def test_schema_version():
    """Schema version is set correctly."""
    assert SCHEMA_VERSION == 2


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
