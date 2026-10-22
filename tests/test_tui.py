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
            assert {hit.status_id for hit in hits.hits} == {"11", "22"}
            rendered = str(hits.render())
            assert app.center is not None
            assert app.center.status_id in rendered
            chrome = str(app.query_one("#chrome").render())
            assert "matches 2" in chrome
            assert app.focused is hits
            app.action_focus_next()
            await pilot.pause()
            assert app.focused is app.query_one("#search")
            app.action_focus_next()
            await pilot.pause()
            assert app.focused is hits
            app.query_one("#search").focus()
            app.action_escape()
            assert app.focused is hits
            app.action_show_help()

    asyncio.run(scenario())


def test_tui_large_result_does_not_mount_one_widget_per_hit(store):
    for index in range(40):
        add_bookmark(store, str(1000 + index), f"relaybench note {index}", handle="ada")

    app = TweetKBApp(store)

    async def scenario() -> None:
        async with app.run_test(size=(100, 30)) as pilot:
            search = app.query_one("#search")
            search.value = "relaybench"
            await search.action_submit()
            await pilot.pause()
            hits = app.query_one("#hits")
            assert app._hit_count == 40
            assert len(list(hits.children)) < app._hit_count
            label = str(app.query_one("#hits_label").render())
            assert "1/40" in label
            assert app.center is not None
            first = app.center.status_id
            await pilot.press("j")
            assert app.center is not None
            assert app.center.status_id != first
            assert "2/40" in str(app.query_one("#hits_label").render())

    asyncio.run(scenario())
