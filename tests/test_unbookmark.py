from __future__ import annotations

from conftest import add_bookmark

from tweetkb.cli import main
from tweetkb.db import Store
from tweetkb.search import search_bookmarks
from tweetkb.unbookmark import click_script, list_unbookmark_candidates, mark_unbookmarked


def test_mark_unbookmarked_keeps_the_local_row_searchable(store):
    add_bookmark(store, "11", "nomic embed text for local RAG", handle="alice")

    mark_unbookmarked(store, "11")

    hits = search_bookmarks(store, "nomic")
    assert [hit.status_id for hit in hits] == ["11"]
    row = store.get_bookmark_by_status("11")
    assert row["review_state"] == "unbookmarked"


def test_unbookmark_search_lists_matching_status_ids(store):
    add_bookmark(store, "11", "nomic embed text", handle="alice")
    add_bookmark(store, "22", "unrelated cooking", handle="bob")

    candidates = list_unbookmark_candidates(store, "nomic")

    assert [item.status_id for item in candidates] == ["11"]


def test_click_script_targets_the_bookmarked_status_button():
    js = click_script("123456789")
    assert "123456789" in js
    assert "removeBookmark" in js
    assert ".click(" in js


def test_unbookmark_cli_without_yes_does_not_apply(db_path, capsys, monkeypatch):
    store = Store(db_path, create=True)
    store.init()
    add_bookmark(store, "11", "nomic embed text", handle="alice")
    store.close()
    clicked = []
    monkeypatch.setattr("tweetkb.unbookmark.unbookmark_on_x", lambda *args, **kwargs: clicked.append(args))

    code = main(["--db", str(db_path), "unbookmark", "--ids", "11"])

    captured = capsys.readouterr()
    assert code == 2
    assert clicked == []
    assert "tweetkb unbookmark --ids 11 --yes" in captured.err


def test_unbookmark_cli_search_prints_copy_paste_ids(db_path, capsys):
    store = Store(db_path, create=True)
    store.init()
    add_bookmark(store, "11", "nomic embed text", handle="alice")
    store.close()

    code = main(["--db", str(db_path), "unbookmark", "--search", "nomic"])

    captured = capsys.readouterr()
    assert code == 0
    assert "11" in captured.out
    assert "alice" in captured.out
