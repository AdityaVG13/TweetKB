from __future__ import annotations

import json

from conftest import add_bookmark

from tweetkb.cli import main
from tweetkb.db import Store
from tweetkb.relations import atlas_payload, author_map, related_bookmarks


def _classify(store, bookmark_id: int, slug: str) -> None:
    store.set_classifications(
        bookmark_id,
        [{"slug": slug, "confidence": 0.9, "method": "test", "rationale": "fixture"}],
        slug,
        0.9,
    )


def test_shared_exact_url_is_same_url_not_just_domain(store):
    a = add_bookmark(store, "11", "see\nhttps://\ngithub.com/foo/bar", handle="alice")
    b = add_bookmark(store, "22", "also\nhttps://\ngithub.com/foo/bar", handle="bob")
    add_bookmark(store, "33", "other\nhttps://\ngithub.com/other/repo", handle="carol")

    hits = related_bookmarks(store, "11", kinds=("url",))

    assert [hit.status_id for hit in hits] == ["22"]
    assert hits[0].kind == "same_url"
    assert hits[0].via == "https://github.com/foo/bar"
    assert a and b


def test_shared_domain_does_not_claim_same_url(store):
    add_bookmark(store, "11", "see\nhttps://\ngithub.com/foo/bar", handle="alice")
    add_bookmark(store, "22", "other\nhttps://\ngithub.com/other/repo", handle="bob")

    urls = related_bookmarks(store, "11", kinds=("url",))
    domains = related_bookmarks(store, "11", kinds=("domain",))

    assert urls == []
    assert [hit.status_id for hit in domains] == ["22"]
    assert domains[0].kind == "same_domain"
    assert domains[0].via == "github.com"


def test_same_author_is_an_edge(store):
    add_bookmark(store, "11", "first note", handle="alice")
    add_bookmark(store, "22", "second note", handle="alice")
    add_bookmark(store, "33", "other person", handle="bob")

    hits = related_bookmarks(store, "11", kinds=("author",))

    assert [hit.status_id for hit in hits] == ["22"]
    assert hits[0].kind == "same_author"
    assert hits[0].via == "alice"


def test_same_category_is_opt_in(store):
    one = add_bookmark(store, "11", "cuda rust kernels", handle="alice")
    two = add_bookmark(store, "22", "borrow checker notes", handle="bob")
    _classify(store, one, "coding")
    _classify(store, two, "coding")

    default = related_bookmarks(store, "11")
    with_cat = related_bookmarks(store, "11", kinds=("cat",))

    assert default == []
    assert [hit.status_id for hit in with_cat] == ["22"]
    assert with_cat[0].kind == "same_cat"


def test_x_profile_host_is_not_a_domain_edge(store):
    add_bookmark(store, "11", "talk", handle="alice", links=("https://x.com/alice",))
    add_bookmark(store, "22", "talk", handle="bob", links=("https://x.com/bob",))

    hits = related_bookmarks(store, "11", kinds=("domain",))

    assert hits == []


def test_unknown_status_id_hard_fails(store):
    add_bookmark(store, "11", "hello", handle="alice")
    try:
        related_bookmarks(store, "999")
    except ValueError as exc:
        assert "999" in str(exc)
    else:
        raise AssertionError("missing status_id must hard-fail")


def test_author_map_groups_domains(store):
    add_bookmark(store, "11", "see\nhttps://\ngithub.com/foo/bar", handle="alice")
    add_bookmark(store, "22", "paper\nhttps://\narxiv.org/abs/1", handle="alice")
    add_bookmark(store, "33", "noise", handle="bob")

    payload = author_map(store, "alice")

    domains = {item["domain"]: item["count"] for item in payload["domains"]}
    assert payload["handle"] == "alice"
    assert payload["total"] == 2
    assert domains["github.com"] == 1
    assert domains["arxiv.org"] == 1


def test_atlas_payload_lists_category_masses(store):
    one = add_bookmark(store, "11", "cuda rust kernels", handle="alice")
    two = add_bookmark(store, "22", "another rust note", handle="bob")
    _classify(store, one, "coding")
    _classify(store, two, "coding")

    payload = atlas_payload(store)

    slugs = {item["slug"]: item["count"] for item in payload["categories"]}
    assert payload["total"] == 2
    assert slugs["coding"] == 2


def test_related_cli_json(db_path, capsys):
    store = Store(db_path, create=True)
    store.init()
    add_bookmark(store, "11", "see\nhttps://\ngithub.com/foo/bar", handle="alice")
    add_bookmark(store, "22", "also\nhttps://\ngithub.com/foo/bar", handle="bob")
    store.close()

    code = main(["--db", str(db_path), "related", "11", "--json"])
    captured = capsys.readouterr()
    assert code == 0
    payload = json.loads(captured.out)
    assert payload["center"] == "11"
    assert payload["edges"][0]["to"] == "22"
    assert payload["edges"][0]["kind"] == "same_url"


def test_atlas_cli_writes_html(db_path, tmp_path, capsys):
    store = Store(db_path, create=True)
    store.init()
    one = add_bookmark(store, "11", "cuda rust kernels", handle="alice")
    _classify(store, one, "coding")
    store.close()
    out = tmp_path / "atlas.html"

    code = main(["--db", str(db_path), "atlas", "--out", str(out)])
    captured = capsys.readouterr()
    assert code == 0
    text = out.read_text()
    assert "coding" in text
    assert "atlas" in captured.out.lower() or str(out) in captured.out


def test_related_missing_database_does_not_create_one(tmp_path, capsys):
    missing = tmp_path / "missing.sqlite3"
    code = main(["--db", str(missing), "related", "11"])
    assert code != 0
    assert not missing.exists()
