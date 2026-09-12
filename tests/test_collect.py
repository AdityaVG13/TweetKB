from __future__ import annotations

import argparse
import shutil

from tweetkb.checkpoint import Checkpoint
from tweetkb.cli import _dispatch, _interactive_command_for_choice
from tweetkb.collector import BrowserHarnessCollector, CollectResult
from tweetkb.db import Store


def test_apple_events_collect_does_not_require_browser_harness(monkeypatch, tmp_path):
    store = Store(tmp_path / "db.sqlite3", create=True)
    store.init()
    collector = BrowserHarnessCollector(store=store, checkpoint=Checkpoint(tmp_path / "checkpoint.json"))
    monkeypatch.setattr(shutil, "which", lambda _name: None)
    monkeypatch.setattr(
        collector,
        "_collect_with_apple_events",
        lambda **_kwargs: {"tweets": [], "batches": 0, "scrollY": 0, "pageHeight": 0, "visibleArticles": 0},
    )

    result = collector.collect(limit=10, apple_events=True, wait_seconds=0.01)

    assert result.saved == 0
    assert result.seen == 0
    store.close()


def test_cli_apple_events_collect_does_not_call_ensure_available(monkeypatch, tmp_path, capsys):
    calls = {"ensure_available": 0}

    class FakeCollector:
        def ensure_available(self):
            calls["ensure_available"] += 1
            raise AssertionError("apple-events collection must not require browser-harness")

        def collect(self, limit, batch_size, wait, **kwargs):
            calls["kwargs"] = kwargs
            calls["limit"] = limit
            return CollectResult(saved=0, seen=0, batches=0)

    db_path = tmp_path / "bookmarks.sqlite3"
    store = Store(db_path, create=True)
    store.init()
    store.close()
    monkeypatch.setattr("tweetkb.cli._make_collector", lambda store, args: FakeCollector())
    args = argparse.Namespace(
        cmd="collect",
        limit=100,
        batch_size=20,
        wait=1.5,
        all=True,
        existing_tab=False,
        normal_chrome=False,
        apple_events=True,
        headless=False,
        stop_at_existing=True,
        stop_after_known=8,
    )

    code = _dispatch(args, db_path)

    assert code == 0
    assert calls["ensure_available"] == 0
    assert calls["limit"] is None
    assert calls["kwargs"]["apple_events"] is True
    assert "browser-harness" not in capsys.readouterr().out


def test_browser_harness_all_script_is_unbounded_and_stops_at_existing(tmp_path):
    collector = BrowserHarnessCollector(
        store=object(),
        checkpoint=Checkpoint(tmp_path / "checkpoint.json"),
    )
    script = collector._browser_script(
        limit=None,
        batch_size=20,
        wait_seconds=0.01,
        existing_tab=False,
        all_bookmarks=True,
        known_status_ids={"123"},
        stop_at_existing=True,
    )

    assert "target_limit = None" in script
    assert "window.__tweetkbOrder = []" in script
    compile(script, "<browser-harness-script>", "exec")


def test_extractor_js_is_valid_javascript(tmp_path):
    collector = BrowserHarnessCollector(
        store=object(),
        checkpoint=Checkpoint(tmp_path / "checkpoint.json"),
    )
    script = collector._extractor_js()
    assert "status" in script
    assert "document" in script or "querySelector" in script


def test_interactive_collect_defaults_to_apple_events():
    command = _interactive_command_for_choice(
        "1",
        input_fn=_answers(["", "y", "", ""]),
    )
    assert command[0] == "collect"
    assert "--apple-events" in command
    assert "--all" in command


def _answers(values):
    iterator = iter(values)
    return lambda _prompt: next(iterator)
