from __future__ import annotations

from tweetkb.collect_runner import (
    RUNNER_JS,
    detect_rate_limit,
    parse_snapshot,
    poll_seconds,
)


def test_rate_limit_wall_is_detected_from_x_copy():
    assert detect_rate_limit("This request looks like it might be automated. Please try again later.")
    assert detect_rate_limit("Sorry, you are rate limited.")
    assert not detect_rate_limit("New browser agent automation workflow with MCP tool use")


def test_snapshot_parser_returns_only_new_items():
    payload = parse_snapshot(
        '{"ok": true, "rate_limited": false, "total": 2, "items": ['
        '{"status_id": "1", "tweet_text": "a"},'
        '{"status_id": "2", "tweet_text": "b"}]}'
    )
    assert payload["ok"] is True
    assert [item["status_id"] for item in payload["items"]] == ["1", "2"]
    assert payload["rate_limited"] is False


def test_poll_slows_when_the_feed_stops_adding_tweets():
    assert poll_seconds(added=20, empty_polls=0) < poll_seconds(added=0, empty_polls=1)
    assert poll_seconds(added=0, empty_polls=2) >= 12


def test_in_page_runner_scrolls_with_settimeout_not_python_ticks():
    assert "setTimeout" in RUNNER_JS
    assert "scrollIntoView" in RUNNER_JS
    assert "removeBookmark" not in RUNNER_JS
