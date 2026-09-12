from __future__ import annotations

from tweetkb.chrome_session import find_bookmarks_tab


def test_find_bookmarks_tab_prefers_history_over_old_bookmarks_alias(monkeypatch):
    listing = "\n".join(
        [
            "1\t1\thttps://github.com/AdityaVG13/TweetKB",
            "1\t2\thttps://x.com/i/bookmarks",
            "2\t1\thttps://x.com/i/history",
        ]
    )
    monkeypatch.setattr("tweetkb.chrome_session.run_osascript", lambda source, timeout=60: listing)
    tab = find_bookmarks_tab("Google Chrome")
    assert tab is not None
    assert tab.window == 2
    assert tab.tab == 1
    assert "/i/history" in tab.url


def test_find_bookmarks_tab_accepts_old_bookmarks_alias(monkeypatch):
    monkeypatch.setattr(
        "tweetkb.chrome_session.run_osascript",
        lambda source, timeout=60: "1\t1\thttps://x.com/i/bookmarks\n",
    )
    tab = find_bookmarks_tab("Google Chrome")
    assert tab is not None
    assert "/i/bookmarks" in tab.url


def test_find_bookmarks_tab_returns_none_when_missing(monkeypatch):
    monkeypatch.setattr(
        "tweetkb.chrome_session.run_osascript",
        lambda source, timeout=60: "1\t1\thttps://github.com/AdityaVG13/TweetKB\n",
    )
    assert find_bookmarks_tab("Google Chrome") is None
