from pathlib import Path

from tweetkb.db import Store
from tweetkb.junk import list_junk_candidates


def test_junk_candidates_flag_x_ads_link(tmp_path: Path):
    store = Store(tmp_path / "db.sqlite3")
    store.init()
    bookmark_id = store.upsert_bookmark(
        {
            "status_url": "https://x.com/a/status/1",
            "author_handle": "a",
            "tweet_text": "Some thin ad policy link",
        }
    )
    assert bookmark_id is not None
    store.set_content_enrichment(
        bookmark_id,
        "https://business.x.com/en/help/troubleshooting/how-x-ads-work",
        "ads policy text",
        source_type="linked-page",
        title="How X ads work",
    )

    candidates = list_junk_candidates(store)

    assert len(candidates) == 1
    assert candidates[0].status_id == "1"
    assert "x-ad" in candidates[0].reason
    store.close()
