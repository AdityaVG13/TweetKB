from pathlib import Path

from tweetkb.classifier import classify_text, embed_text
from tweetkb.db import Store
from tweetkb.exporter import export_obsidian, note_filename


def test_classifier_detects_agents():
    result = classify_text("New browser agent automation workflow with MCP tool use", [])
    assert result["category"] == "ai-agents"
    assert result["confidence"] > 0.5
    assert "ai-agents" in result["tags"]


def test_embedding_dims():
    assert len(embed_text("hello world", dims=16)) == 16


def test_obsidian_export(tmp_path: Path):
    store = Store(tmp_path / "db.sqlite3")
    store.init()
    bookmark_id = store.upsert_bookmark({"status_url": "https://x.com/a/status/1", "tweet_text": "AI agent tool"})
    assert bookmark_id
    result = classify_text("AI agent tool", [])
    store.update_classification(bookmark_id, result)
    count = export_obsidian(store, tmp_path / "vault")
    assert count == 1
    notes = list((tmp_path / "vault" / "Bookmarks").glob("*.md"))
    assert len(notes) == 1
    assert "status_id" in notes[0].read_text()
    store.close()


def test_obsidian_export_excludes_category(tmp_path: Path):
    store = Store(tmp_path / "db.sqlite3")
    store.init()
    bookmark_id = store.upsert_bookmark({"status_url": "https://x.com/a/status/1", "tweet_text": "random"})
    assert bookmark_id
    store.conn.execute("UPDATE bookmarks SET category = 'misc' WHERE id = ?", (bookmark_id,))
    store.conn.commit()
    count = export_obsidian(store, tmp_path / "vault", exclude_categories={"misc"})
    assert count == 0
    assert list((tmp_path / "vault" / "Bookmarks").glob("*.md")) == []
    store.close()


def test_obsidian_export_includes_category(tmp_path: Path):
    store = Store(tmp_path / "db.sqlite3")
    store.init()
    agent_id = store.upsert_bookmark({"status_url": "https://x.com/a/status/1", "tweet_text": "agent"})
    misc_id = store.upsert_bookmark({"status_url": "https://x.com/a/status/2", "tweet_text": "misc"})
    assert agent_id and misc_id
    store.conn.execute("UPDATE bookmarks SET category = 'ai-agents' WHERE id = ?", (agent_id,))
    store.conn.execute("UPDATE bookmarks SET category = 'misc' WHERE id = ?", (misc_id,))
    store.conn.commit()
    count = export_obsidian(store, tmp_path / "vault", include_categories={"ai-agents"})
    assert count == 1
    assert len(list((tmp_path / "vault" / "Bookmarks").glob("*.md"))) == 1
    store.close()


def test_note_filename_contains_status_id(tmp_path: Path):
    store = Store(tmp_path / "db.sqlite3")
    store.init()
    bookmark_id = store.upsert_bookmark({"status_url": "https://x.com/a/status/99", "tweet_text": "Hello filename"})
    row = store.get_bookmark(bookmark_id)
    assert note_filename(row).startswith("99-")
    store.close()
