from __future__ import annotations

import json

from tweetkb.db import Store
from tweetkb.media_export import export_media_bundle


def test_media_export_writes_bundle_without_api_key(tmp_path, monkeypatch):
    store = Store(tmp_path / "db.sqlite3")
    store.init()
    bookmark_id = store.upsert_bookmark(
        {
            "status_url": "https://x.com/alice/status/123",
            "author_handle": "alice",
            "tweet_text": "Look at this chart",
        }
    )
    assert bookmark_id is not None
    store.set_content_enrichment(
        bookmark_id,
        "https://x.com/alice/status/123",
        "Look at this chart",
        metadata={
            "media": [
                {
                    "url": "https://pbs.twimg.com/media/chart.jpg?format=jpg&name=large",
                    "alt": "Revenue chart",
                }
            ]
        },
    )

    class FakeResponse:
        headers = {"Content-Type": "image/jpeg"}

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self, *_args):
            return b"image-bytes"

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr("tweetkb.media_export.urllib.request.urlopen", lambda request, timeout: FakeResponse())

    result = export_media_bundle(store, tmp_path / "media-review")

    assert result.tweets == 1
    assert result.images == 1
    assert result.downloaded == 1
    manifest = (tmp_path / "media-review" / "manifest.jsonl").read_text().splitlines()
    row = json.loads(manifest[0])
    assert row["status_url"] == "https://x.com/alice/status/123"
    assert row["alt"] == "Revenue chart"
    assert (tmp_path / "media-review" / row["file"]).read_bytes() == b"image-bytes"
    assert "Open `manifest.jsonl`" in (tmp_path / "media-review" / "AI_REVIEW_PROMPT.md").read_text()
    store.close()


def test_media_export_manifest_only_does_not_download(tmp_path, monkeypatch):
    store = Store(tmp_path / "db.sqlite3")
    store.init()
    bookmark_id = store.upsert_bookmark({"status_url": "https://x.com/a/status/1", "tweet_text": "pic"})
    assert bookmark_id is not None
    store.set_content_enrichment(
        bookmark_id,
        "https://x.com/a/status/1",
        "pic",
        metadata={"media": [{"url": "https://pbs.twimg.com/media/a.jpg?format=jpg", "alt": ""}]},
    )
    monkeypatch.setattr(
        "tweetkb.media_export.urllib.request.urlopen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should not download")),
    )

    result = export_media_bundle(store, tmp_path / "media-review", download=False)

    assert result.downloaded == 0
    row = json.loads((tmp_path / "media-review" / "manifest.jsonl").read_text().splitlines()[0])
    assert row["downloaded"] is False
    store.close()
