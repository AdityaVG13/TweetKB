from __future__ import annotations

from tweetkb.analyzer import run_analysis
from tweetkb.db import Store


def test_analysis_classifies_tweet_text_not_dom_chrome(tmp_path):
    store = Store(tmp_path / "db.sqlite3", create=True)
    store.init()
    store.upsert_bookmark(
        {
            "status_url": "https://x.com/chef/status/1",
            "author_handle": "chef",
            "tweet_text": "best focaccia recipe with olive oil",
            "raw_text": "best focaccia recipe with olive oil\nReply\nRepost\nMCP agent tool use browser harness",
        }
    )

    result = run_analysis(store, stage="classify", changed_only=False)
    primary = store.conn.execute(
        "SELECT category_slug FROM classifications WHERE is_primary = 1"
    ).fetchone()

    assert result["classified"] == 1
    assert primary["category_slug"] != "ai-agents"
    store.close()
