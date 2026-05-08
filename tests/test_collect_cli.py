from __future__ import annotations

import argparse
import subprocess

from tweetkb.checkpoint import Checkpoint
from tweetkb.cli import _dispatch
from tweetkb.collector import BrowserHarnessCollector, CollectResult, find_normal_chrome_cdp_ws


def test_collect_all_dispatch_uses_unbounded_limit(monkeypatch, tmp_path, capsys):
    calls = {}

    class FakeCollector:
        def ensure_available(self):
            calls["ensure_available"] = True

        def collect(self, limit, batch_size, wait, **kwargs):
            calls["limit"] = limit
            calls["batch_size"] = batch_size
            calls["wait"] = wait
            calls["kwargs"] = kwargs
            return CollectResult(saved=0, seen=0, batches=0)

    monkeypatch.setattr("tweetkb.cli._make_collector", lambda store, args: FakeCollector())
    args = argparse.Namespace(
        cmd="collect",
        limit=100,
        batch_size=20,
        wait=1.5,
        all=True,
        existing_tab=False,
        normal_chrome=False,
        apple_events=False,
        stop_at_existing=True,
    )

    assert _dispatch(args, tmp_path / "bookmarks.sqlite3") == 0

    assert calls["ensure_available"] is True
    assert calls["limit"] is None
    assert calls["batch_size"] == 20
    assert calls["wait"] == 1.5
    assert calls["kwargs"]["all_bookmarks"] is True
    assert calls["kwargs"]["stop_at_existing"] is True
    output = capsys.readouterr().out
    assert "collect: limit=all" in output
    assert "will stop once already-saved bookmark history is reached" in output
    assert "no AI model or cloud API is used" in output


def test_browser_harness_all_script_is_unbounded(tmp_path):
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
    )

    assert "target_limit = None" in script
    assert "while batches < 5000 and stagnant < 10:" in script
    assert "tweetkb progress:" in script
    compile(script, "<browser-harness-script>", "exec")


def test_browser_harness_all_script_stops_after_existing_history(tmp_path):
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
        known_status_ids={"2", "1"},
        stop_at_existing=True,
    )

    assert "known_status_ids = set(['1', '2'])" in script
    assert "new_count = sum(1 for status_id in seen if status_id not in known_status_ids)" in script
    assert "if existing_stagnant >= 5:" in script
    assert "tweetkb progress: seen={} new={}" in script
    compile(script, "<browser-harness-script>", "exec")


def test_browser_harness_all_script_can_disable_existing_history_stop(tmp_path):
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
        known_status_ids={"1"},
        stop_at_existing=False,
    )

    assert "if False and len(seen) > 0 and new_count == previous_new_count:" in script
    compile(script, "<browser-harness-script>", "exec")


def test_browser_harness_limited_script_keeps_target_limit(tmp_path):
    collector = BrowserHarnessCollector(
        store=object(),
        checkpoint=Checkpoint(tmp_path / "checkpoint.json"),
    )

    script = collector._browser_script(
        limit=25,
        batch_size=20,
        wait_seconds=0.01,
        existing_tab=False,
        all_bookmarks=False,
    )

    assert "target_limit = 25" in script
    assert "while batches < 200 and stagnant < 5:" in script
    compile(script, "<browser-harness-script>", "exec")


def test_normal_chrome_cdp_auto_starts_debug(monkeypatch, tmp_path):
    calls = {}

    monkeypatch.setattr("tweetkb.collector.find_cdp_ws_on_port", lambda port: None)
    monkeypatch.setattr("tweetkb.collector.normal_chrome_has_debugging_flag", lambda browser_app: False)

    def fake_start_normal_chrome_debug(**kwargs):
        calls["start"] = kwargs

    monkeypatch.setattr("tweetkb.collector.start_normal_chrome_debug", fake_start_normal_chrome_debug)
    monkeypatch.setattr("tweetkb.collector.wait_for_normal_chrome_cdp_ws", lambda profile_root, debug_port: "ws://debug")

    ws = find_normal_chrome_cdp_ws(
        profile_root=tmp_path,
        debug_port=9222,
        browser_app="Google Chrome",
        auto_start_debug=True,
    )

    assert ws == "ws://debug"
    assert calls["start"] == {
        "open_bookmarks": True,
        "browser_app": "Google Chrome",
        "browser_profile": tmp_path,
        "debug_port": 9222,
    }


def test_normal_chrome_collect_falls_back_to_apple_events(monkeypatch, tmp_path, capsys):
    class FakeStore:
        def log_event(self, *_args, **_kwargs):
            pass

    collector = BrowserHarnessCollector(FakeStore(), checkpoint=Checkpoint(tmp_path / "checkpoint.json"))
    monkeypatch.setattr(collector, "ensure_available", lambda: None)
    monkeypatch.setattr(
        "tweetkb.collector.find_normal_chrome_cdp_ws",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("CDP not reachable")),
    )
    monkeypatch.setattr("tweetkb.collector._apple_events_javascript_available", lambda _browser_app: True)
    monkeypatch.setattr(
        collector,
        "_collect_with_apple_events",
        lambda **_kwargs: {"items": [], "batches": 0},
    )

    result = collector.collect(normal_chrome=True, all_bookmarks=True)

    assert result.saved == 0
    assert "falling back to Apple Events" in capsys.readouterr().out


def test_apple_events_collect_applies_limit(monkeypatch, tmp_path):
    saved_items = []

    class FakeStore:
        def upsert_bookmark_with_status(self, item):
            saved_items.append(item)
            return len(saved_items), True

        def log_event(self, *_args, **_kwargs):
            pass

    collector = BrowserHarnessCollector(FakeStore(), checkpoint=Checkpoint(tmp_path / "checkpoint.json"))
    monkeypatch.setattr(collector, "ensure_available", lambda: None)
    monkeypatch.setattr(
        collector,
        "_collect_with_apple_events",
        lambda **_kwargs: {
            "items": [
                {"status_id": "1", "status_url": "https://x.com/a/status/1", "tweet_text": "one"},
                {"status_id": "2", "status_url": "https://x.com/a/status/2", "tweet_text": "two"},
            ],
            "batches": 1,
        },
    )

    result = collector.collect(limit=1, apple_events=True)

    assert result.saved == 1
    assert [item["status_id"] for item in saved_items] == ["1"]


def test_apple_events_known_ids_are_escaped_in_applescript(monkeypatch, tmp_path):
    scripts = []

    class FakeStore:
        def log_event(self, *_args, **_kwargs):
            pass

    def fake_run(args, input, **_kwargs):
        scripts.append(input)
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout='TWEETKB_JSON={"items":[],"batches":0}',
            stderr="",
        )

    collector = BrowserHarnessCollector(FakeStore(), checkpoint=Checkpoint(tmp_path / "checkpoint.json"))
    monkeypatch.setattr("tweetkb.collector.subprocess.run", fake_run)

    collector._collect_with_apple_events(
        limit=None,
        batch_size=20,
        wait_seconds=1.5,
        all_bookmarks=True,
        known_status_ids={"1234567890123456789"},
        stop_at_existing=True,
    )

    script = scripts[0]
    assert 'window.__tweetkbKnown = {\\"1234567890123456789\\": true}' in script
    assert 'window.__tweetkbKnown = {"1234567890123456789": true}' not in script
