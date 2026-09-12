from __future__ import annotations

import json

from conftest import add_bookmark

from tweetkb.cli import main
from tweetkb.db import Store
from tweetkb.search import search_bookmarks


def test_search_returns_the_bookmark_whose_tweet_text_contains_the_query(store):
    add_bookmark(store, "11", "nomic embed text for local RAG", handle="alice")
    add_bookmark(store, "22", "unrelated cooking recipe", handle="bob")

    hits = search_bookmarks(store, "nomic")

    assert [hit.status_id for hit in hits] == ["11"]
    assert hits[0].author_handle == "alice"
    assert "nomic" in hits[0].snippet.lower()


def test_search_finds_tokens_in_author_handle(store):
    add_bookmark(store, "11", "hello world", handle="karpathy")
    add_bookmark(store, "22", "hello world", handle="alice")

    hits = search_bookmarks(store, "karpathy")

    assert [hit.status_id for hit in hits] == ["11"]


def test_search_finds_text_only_present_in_enrichment(store):
    bookmark_id = add_bookmark(store, "11", "short tweet", handle="alice")
    add_bookmark(store, "22", "another short tweet", handle="bob")
    store.set_content_enrichment(
        bookmark_id,
        source_url="https://example.com/paper",
        source_type="linked-page",
        title="Attention Is All You Need",
        content_text="The transformer architecture replaces recurrence with self-attention.",
    )

    hits = search_bookmarks(store, "transformer")

    assert [hit.status_id for hit in hits] == ["11"]
    assert "transformer" in hits[0].snippet.lower()


def test_search_and_query_requires_every_token(store):
    add_bookmark(store, "11", "local sqlite knowledge base", handle="alice")
    add_bookmark(store, "22", "local postgres replica", handle="bob")
    add_bookmark(store, "33", "sqlite backup script", handle="carol")

    hits = search_bookmarks(store, "local sqlite")

    assert [hit.status_id for hit in hits] == ["11"]


def test_empty_search_query_raises(store):
    add_bookmark(store, "11", "hello")

    try:
        search_bookmarks(store, "   ")
    except ValueError as exc:
        assert "search query" in str(exc).lower()
    else:
        raise AssertionError("empty search query must hard-fail")


def test_search_cli_prints_matching_status_id(db_path, capsys):
    store = Store(db_path, create=True)
    store.init()
    add_bookmark(store, "99", "browser harness collection from bookmarks", handle="dev")
    store.close()

    code = main(["--db", str(db_path), "search", "harness"])

    captured = capsys.readouterr()
    assert code == 0
    assert "99" in captured.out
    assert "dev" in captured.out


def test_search_cli_empty_query_exits_nonzero(db_path, capsys):
    store = Store(db_path, create=True)
    store.init()
    store.close()

    code = main(["--db", str(db_path), "search", ""])

    captured = capsys.readouterr()
    assert code != 0
    assert "search query" in (captured.err + captured.out).lower()


def test_search_cli_missing_database_does_not_create_one(tmp_path, capsys):
    missing = tmp_path / "missing.sqlite3"

    code = main(["--db", str(missing), "search", "nomic"])

    captured = capsys.readouterr()
    assert code != 0
    assert not missing.exists()
    assert "tweetkb init" in (captured.err + captured.out).lower()


def test_from_query_filters_author_and_keeps_other_authors_out(store):
    add_bookmark(store, "11", "rust compiler notes", handle="alice")
    add_bookmark(store, "22", "rust compiler notes", handle="bob")

    hits = search_bookmarks(store, "from:alice rust")

    assert [hit.status_id for hit in hits] == ["11"]


def test_category_filter_excludes_other_primary_categories(store):
    coding = add_bookmark(store, "11", "sqlite fts search", handle="alice")
    add_bookmark(store, "22", "sqlite fts search", handle="bob")
    store.set_classifications(
        coding,
        [{"slug": "coding", "confidence": 0.9, "method": "keyword"}],
        "coding",
        0.9,
    )

    hits = search_bookmarks(store, "sqlite", category="coding")

    assert [hit.status_id for hit in hits] == ["11"]
    assert hits[0].category == "coding"


def test_denser_match_ranks_above_a_newer_weak_match(store):
    add_bookmark(store, "11", "rust rust rust compiler internals", handle="old", captured_at="2020-01-01T00:00:00+00:00")
    add_bookmark(store, "22", "I mentioned rust once", handle="new", captured_at="2026-01-01T00:00:00+00:00")

    hits = search_bookmarks(store, "rust")

    assert hits[0].status_id == "11"


def test_search_cli_json_is_parseable_and_empty_hits_exit_zero(db_path, capsys):
    store = Store(db_path, create=True)
    store.init()
    add_bookmark(store, "99", "browser harness collection from bookmarks", handle="dev")
    store.close()

    code = main(["--db", str(db_path), "search", "harness", "--json"])
    captured = capsys.readouterr()
    assert code == 0
    payload = json.loads(captured.out)
    assert payload["hits"][0]["status_id"] == "99"
    assert payload["hits"][0]["author_handle"] == "dev"
    assert captured.err == ""

    code = main(["--db", str(db_path), "search", "zzzz-no-such-token", "--json"])
    captured = capsys.readouterr()
    assert code == 0
    assert json.loads(captured.out) == {"count": 0, "hits": []}


def test_find_is_an_alias_for_search(db_path, capsys):
    store = Store(db_path, create=True)
    store.init()
    add_bookmark(store, "99", "nomic embed text", handle="alice")
    store.close()

    code = main(["--db", str(db_path), "find", "nomic", "--json"])
    captured = capsys.readouterr()
    assert code == 0
    assert json.loads(captured.out)["hits"][0]["status_id"] == "99"


def test_search_open_uses_system_opener_for_top_hit(db_path, capsys, monkeypatch):
    store = Store(db_path, create=True)
    store.init()
    add_bookmark(store, "99", "browser harness collection", handle="dev")
    store.close()
    opened = []
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/open" if name == "open" else None)
    monkeypatch.setattr("subprocess.run", lambda cmd, check=False: opened.append(cmd))

    code = main(["--db", str(db_path), "search", "harness", "--open"])

    assert code == 0
    assert opened == [["/usr/bin/open", "https://x.com/dev/status/99"]]


def test_search_finds_token_only_present_in_reconstructed_link(store):
    add_bookmark(store, "11", "Make me happy\nhttps://\ngithub.com/kossnocorp/gen\notype", handle="alice")
    add_bookmark(store, "22", "unrelated cooking recipe", handle="bob")

    hits = search_bookmarks(store, "genotype")

    assert [hit.status_id for hit in hits] == ["11"]


def test_link_domain_filter_keeps_only_that_host(store):
    add_bookmark(store, "11", "paper\nhttps://\narxiv.org/abs/2609.04981", handle="alice")
    add_bookmark(store, "22", "code\nhttps://\ngithub.com/foo/bar", handle="bob")

    hits = search_bookmarks(store, "link:arxiv.org")

    assert [hit.status_id for hit in hits] == ["11"]


def test_search_sorts_by_posted_time_not_saved_time(store):
    add_bookmark(
        store,
        "11",
        "rust notes",
        handle="old",
        captured_at="2026-09-01T00:00:00+00:00",
        created_at="2018-01-01T00:00:00+00:00",
    )
    add_bookmark(
        store,
        "22",
        "rust notes",
        handle="new",
        captured_at="2020-01-01T00:00:00+00:00",
        created_at="2026-08-01T00:00:00+00:00",
    )

    posted = search_bookmarks(store, "rust", sort="posted")
    saved = search_bookmarks(store, "rust", sort="saved")

    assert [hit.status_id for hit in posted] == ["22", "11"]
    assert [hit.status_id for hit in saved] == ["11", "22"]


def test_saved_window_excludes_old_captures(store):
    add_bookmark(
        store,
        "11",
        "rust notes",
        handle="old",
        captured_at="2020-01-01T00:00:00+00:00",
    )
    add_bookmark(
        store,
        "22",
        "rust notes",
        handle="new",
        captured_at="2026-09-01T00:00:00+00:00",
    )

    hits = search_bookmarks(store, "rust saved:7d", now="2026-09-03T00:00:00+00:00")

    assert [hit.status_id for hit in hits] == ["22"]


def test_search_rust_does_not_match_trust(store):
    add_bookmark(store, "11", "trust him on the economy", handle="old")
    add_bookmark(store, "22", "write cuda kernels in rust", handle="new")

    hits = search_bookmarks(store, "rust")

    assert [hit.status_id for hit in hits] == ["22"]


def test_search_json_includes_outbound_url(db_path, capsys):
    store = Store(db_path, create=True)
    store.init()
    add_bookmark(store, "11", "see\nhttps://\ngithub.com/foo/bar", handle="alice")
    store.close()

    code = main(["--db", str(db_path), "search", "foo", "--json"])
    captured = capsys.readouterr()
    assert code == 0
    hit = json.loads(captured.out)["hits"][0]
    assert "https://github.com/foo/bar" in hit["outbound_links"]


def test_search_human_output_joins_split_https_scheme(db_path, capsys):
    store = Store(db_path, create=True)
    store.init()
    add_bookmark(store, "11", "see\nhttps://\ngithub.com/foo/bar", handle="alice")
    store.close()

    code = main(["--db", str(db_path), "search", "foo"])
    captured = capsys.readouterr()
    assert code == 0
    assert "https:// github.com" not in captured.out
    assert "https://github.com/foo/bar" in captured.out

