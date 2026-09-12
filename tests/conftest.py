from __future__ import annotations

from pathlib import Path

import pytest

from tweetkb.db import Store


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "bookmarks.sqlite3"


@pytest.fixture
def store(db_path: Path) -> Store:
    db = Store(db_path, create=True)
    db.init()
    yield db
    db.close()


def add_bookmark(
    store: Store,
    status_id: str = "1",
    text: str = "hello",
    handle: str = "alice",
    *,
    raw_text: str | None = None,
    links: tuple[str, ...] = (),
    captured_at: str | None = None,
    created_at: str | None = None,
) -> int:
    payload = {
        "status_url": f"https://x.com/{handle}/status/{status_id}",
        "author_handle": handle,
        "author_name": handle.title(),
        "tweet_text": text,
        "raw_text": raw_text if raw_text is not None else text,
        "links": list(links),
    }
    if captured_at:
        payload["captured_at"] = captured_at
    if created_at:
        payload["created_at"] = created_at
    result = store.upsert_bookmark(payload)
    assert result is not None
    return int(result)
