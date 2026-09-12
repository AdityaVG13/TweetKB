from __future__ import annotations

from tweetkb.collect_pace import sleep_seconds


class _Seq:
    def __init__(self, values):
        self.values = list(values)

    def uniform(self, lo, hi):
        if not self.values:
            return (lo + hi) / 2
        return self.values.pop(0)


def test_all_collect_wait_is_slower_than_the_requested_base():
    wait = sleep_seconds(0.7, batch=1, all_bookmarks=True, rng=_Seq([0.5]))
    assert wait >= 2.5


def test_all_collect_inserts_a_rest_every_thirty_batches():
    rest = sleep_seconds(0.7, batch=30, all_bookmarks=True, rng=_Seq([0.5, 20.0]))
    no_rest = sleep_seconds(0.7, batch=29, all_bookmarks=True, rng=_Seq([0.5]))
    assert rest - no_rest >= 15


def test_limited_collect_keeps_the_requested_wait():
    wait = sleep_seconds(0.8, batch=1, all_bookmarks=False, rng=_Seq([0.1]))
    assert 0.8 <= wait < 1.5
