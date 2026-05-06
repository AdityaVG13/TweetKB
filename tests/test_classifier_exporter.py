from pathlib import Path

from tweetkb.classifier import classify_text, embed_text
from tweetkb.db import Store
from tweetkb.exporters.obsidian import _note_filename as note_filename
from tweetkb.exporters.obsidian import export_obsidian


def test_classifier_detects_agents():
    result = classify_text("New browser agent automation workflow with MCP tool use", [])
    assert result["primary"] == "ai-agents"
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
    store.set_classifications(bookmark_id, result["categories"], result["primary"], result["confidence"])
    store.update_bookmark_analysis(bookmark_id, summary=result.get("summary", ""), why_it_matters=result.get("why_it_matters", ""))
    count, skipped = export_obsidian(store, tmp_path / "vault")
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
    # Set classification to misc
    store.set_classifications(bookmark_id, [{"slug": "misc", "confidence": 0.9, "method": "test"}], "misc", 0.9)
    count, skipped = export_obsidian(store, tmp_path / "vault", exclude_categories={"misc"})
    assert count == 0
    assert list((tmp_path / "vault" / "Bookmarks").glob("*.md")) == []
    store.close()


def test_obsidian_export_includes_category(tmp_path: Path):
    store = Store(tmp_path / "db.sqlite3")
    store.init()
    agent_id = store.upsert_bookmark({"status_url": "https://x.com/a/status/1", "tweet_text": "agent"})
    misc_id = store.upsert_bookmark({"status_url": "https://x.com/a/status/2", "tweet_text": "misc"})
    assert agent_id and misc_id
    store.set_classifications(agent_id, [{"slug": "ai-agents", "confidence": 0.9, "method": "test"}], "ai-agents", 0.9)
    store.set_classifications(misc_id, [{"slug": "misc", "confidence": 0.9, "method": "test"}], "misc", 0.9)
    count, skipped = export_obsidian(store, tmp_path / "vault", include_categories={"ai-agents"})
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
