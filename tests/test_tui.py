from __future__ import annotations

import asyncio

from conftest import add_bookmark

from tweetkb.db import Store
from tweetkb.tui_app import TweetKBApp


def _classify(store: Store, bookmark_id: int, slug: str) -> None:
    store.set_classifications(
        bookmark_id,
        [{"slug": slug, "confidence": 0.9, "method": "test", "rationale": "fixture"}],
        slug,
        0.9,
    )


def test_tui_boot_shows_category_meter(store):
    one = add_bookmark(store, "11", "cuda rust kernels", handle="alice")
    _classify(store, one, "coding")
    add_bookmark(store, "22", "also rust notes\nhttps://\ngithub.com/foo/bar", handle="bob")

    app = TweetKBApp(store)

    async def scenario() -> None:
        async with app.run_test() as pilot:
            await pilot.pause()
            meters = app.query_one("#meters")
            text = str(meters.render())
            assert "coding" in text
            search = app.query_one("#search")
            search.value = "rust"
            await search.action_submit()
            await pilot.pause()
            hits = app.query_one("#hits")
            assert len(list(hits.children)) >= 1

    asyncio.run(scenario())
