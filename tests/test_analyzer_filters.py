from tweetkb.analyzer import run_analysis
from tweetkb.db import Store


def test_analysis_can_include_existing_categories(tmp_path):
    store = Store(tmp_path / "db.sqlite3")
    store.init()
    agent_id = store.upsert_bookmark({"status_url": "https://x.com/a/status/1", "tweet_text": "OpenAI agent SDK"})
    misc_id = store.upsert_bookmark({"status_url": "https://x.com/a/status/2", "tweet_text": "random note"})
    assert agent_id and misc_id
    store.set_classifications(agent_id, [{"slug": "ai-agents", "confidence": 0.9, "method": "test"}], "ai-agents", 0.9)
    store.set_classifications(misc_id, [{"slug": "misc", "confidence": 0.9, "method": "test"}], "misc", 0.9)

    result = run_analysis(store, stage="entities", changed_only=False, include_categories={"ai-agents"})

    assert result["selected"] == 1
    assert result["total"] == 1
    assert store.get_bookmark_entities(agent_id)
    assert store.get_bookmark_entities(misc_id) == []
    store.close()


def test_analysis_can_limit_selection(tmp_path):
    store = Store(tmp_path / "db.sqlite3")
    store.init()
    for idx in range(3):
        bookmark_id = store.upsert_bookmark(
            {"status_url": f"https://x.com/a/status/{idx + 1}", "tweet_text": f"OpenAI agent {idx}"}
        )
        assert bookmark_id

    result = run_analysis(store, stage="classify", changed_only=False, limit=2)

    assert result["selected"] == 2
    assert result["total"] == 2
    assert len([row for row in store.list_bookmarks() if store.get_bookmark_classifications(int(row["id"]))]) == 2
    store.close()


def test_analysis_reports_progress(tmp_path):
    store = Store(tmp_path / "db.sqlite3")
    store.init()
    bookmark_id = store.upsert_bookmark({"status_url": "https://x.com/a/status/1", "tweet_text": "OpenAI agent"})
    assert bookmark_id
    messages: list[str] = []

    run_analysis(store, stage="classify", changed_only=False, progress=messages.append)

    assert messages[0] == "analysis: selected=1 stage=classify provider=local-hash"
    assert messages[1] == "analysis: 1/1 processing 1"
    store.close()
