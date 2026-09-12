from __future__ import annotations

import json

from conftest import add_bookmark

from tweetkb.cli import main
from tweetkb.db import Store
from tweetkb.digest import build_digest


def test_digest_lists_github_as_a_top_domain(store):
    add_bookmark(store, "11", "see\nhttps://\ngithub.com/foo/bar", handle="alice")
    add_bookmark(store, "22", "paper\nhttps://\narxiv.org/abs/1", handle="bob")
    add_bookmark(store, "33", "no links here just chat", handle="carol")

    payload = build_digest(store)

    domains = {item["domain"]: item["count"] for item in payload["domains"]}
    assert domains["github.com"] == 1
    assert domains["arxiv.org"] == 1
    assert payload["total"] == 3
    assert "x.com" not in domains


def test_digest_counts_thin_tweets_and_real_outbound(store):
    add_bookmark(store, "11", "yay", handle="alice")
    add_bookmark(store, "22", "see\nhttps://\ngithub.com/foo/bar", handle="bob")

    payload = build_digest(store)

    assert payload["thin"] == 1
    assert payload["with_outbound"] == 1


def test_digest_cli_json_lists_domains(db_path, capsys):
    store = Store(db_path, create=True)
    store.init()
    add_bookmark(store, "11", "see\nhttps://\ngithub.com/foo/bar", handle="alice")
    store.close()

    code = main(["--db", str(db_path), "digest", "--json"])
    captured = capsys.readouterr()
    assert code == 0
    payload = json.loads(captured.out)
    domains = {item["domain"]: item["count"] for item in payload["domains"]}
    assert domains["github.com"] == 1
