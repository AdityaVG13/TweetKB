from __future__ import annotations

from tweetkb.collect_stop import decide_scroll_stop, leading_known_count, trailing_known_streak


def test_rebookmarked_old_tweets_at_the_top_do_not_stop_collection():
    known = {"old-a", "old-b", "old-c"}
    ordered = ["old-a", "old-b", "brand-new", "also-new"]

    assert leading_known_count(ordered, known) == 2
    assert trailing_known_streak(ordered, known) == 0
    decision = decide_scroll_stop(ordered, known, empty_scrolls=0, known_streak=8)
    assert decision.stop is False


def test_stop_when_older_end_is_a_run_of_already_saved_ids():
    known = {f"old-{i}" for i in range(8)}
    ordered = ["fresh"] + [f"old-{i}" for i in range(8)]

    decision = decide_scroll_stop(ordered, known, empty_scrolls=0, known_streak=8)
    assert decision.stop is True
    assert decision.reason == "known_streak"


def test_all_known_prefix_keeps_scrolling_until_feed_ends():
    known = {"a", "b", "c"}
    ordered = ["a", "b", "c"]

    decision = decide_scroll_stop(ordered, known, empty_scrolls=3, known_streak=8)
    assert decision.stop is False
    assert decision.reason == "continue"


def test_end_of_feed_is_no_new_dom_items():
    decision = decide_scroll_stop(["a"], set(), empty_scrolls=10, known_streak=8)
    assert decision.stop is True
    assert decision.reason == "end_of_feed"


def test_one_duplicate_bookmark_is_not_a_known_streak():
    known = {"same"}
    ordered = ["same", "new-1", "new-2", "same"]
    assert trailing_known_streak(ordered, known) == 1
    decision = decide_scroll_stop(ordered, known, empty_scrolls=0, known_streak=8)
    assert decision.stop is False


def test_merge_batch_accumulates_ids_that_leave_the_virtualized_dom():
    from tweetkb.collect_stop import merge_batch

    acc_order, acc_items, added = merge_batch([], {}, [{"status_id": "1", "tweet_text": "a"}, {"status_id": "2", "tweet_text": "b"}])
    acc_order, acc_items, added = merge_batch(
        acc_order,
        acc_items,
        [{"status_id": "2", "tweet_text": "b"}, {"status_id": "3", "tweet_text": "c"}],
    )
    assert acc_order == ["1", "2", "3"]
    assert added == 1
    assert set(acc_items) == {"1", "2", "3"}
