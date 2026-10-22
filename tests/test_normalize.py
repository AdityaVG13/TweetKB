from __future__ import annotations

from conftest import add_bookmark

from tweetkb.normalize import clean_tweet_text, normalize_collected_item, outbound_links


def test_clean_tweet_text_drops_x_chrome_lines():
    raw = "\n".join(
        [
            "Alice",
            "@alice",
            "browser-harness should not require CDP",
            "Reply",
            "12",
            "Repost",
            "Like",
            "Bookmark",
            "1.2K",
        ]
    )
    assert clean_tweet_text(raw) == "Alice\n@alice\nbrowser-harness should not require CDP"


def test_outbound_links_drop_analytics_and_self_status():
    links = outbound_links(
        [
            "https://x.com/alice/status/1",
            "https://x.com/alice/status/1/analytics",
            "https://x.com/i/history",
            "https://github.com/browser-use/browser-harness",
        ],
        status_url="https://x.com/alice/status/1",
    )
    assert links == ["https://github.com/browser-use/browser-harness"]


def test_outbound_links_drop_profile_urls_but_keep_github():
    links = outbound_links(
        ["https://x.com/alice", "https://github.com/foo/bar"],
        status_url="https://x.com/alice/status/1",
    )
    assert links == ["https://github.com/foo/bar"]


def test_urls_from_tweet_text_join_split_https_lines():
    from tweetkb.normalize import urls_from_tweet_text

    urls = urls_from_tweet_text("see this\nhttps://\nfixture.example/aesthetics")
    assert urls == ["https://fixture.example/aesthetics"]


def test_urls_from_tweet_text_joins_wrapped_github_path():
    from tweetkb.normalize import urls_from_tweet_text

    urls = urls_from_tweet_text(
        "or use:\nhttps://\ngithub.com/example/gos\nhipit\nsee the repo"
    )
    assert urls == ["https://github.com/example/goshipit"]


def test_urls_from_tweet_text_drops_host_without_a_dot():
    from tweetkb.normalize import urls_from_tweet_text

    assert urls_from_tweet_text("see\nhttps://\npub-ae") == []
    assert urls_from_tweet_text("code\nhttps://\ntrain.py") == []


def test_repair_links_replaces_implausible_hosts(store):
    from tweetkb.normalize import repair_links_from_text

    bookmark_id = add_bookmark(store, "11", "see\nhttps://\nfixture.example/aesthetics")
    store._store_bookmark_links(bookmark_id, ("https://pub-ae",))

    repair_links_from_text(store)

    urls = [row["url"] for row in store.get_bookmark_links(bookmark_id)]
    assert "https://pub-ae" not in urls
    assert "https://fixture.example/aesthetics" in urls


def test_normalize_collected_item_requires_status_and_body():
    assert normalize_collected_item({"status_url": "https://x.com/a/status/1", "tweet_text": ""}) is None
    item = normalize_collected_item(
        {
            "status_url": "https://x.com/alice/status/99",
            "status_id": "99",
            "author_handle": "@alice",
            "author_name": "Alice\n@alice",
            "tweet_text": "hello world\nReply",
            "raw_text": "Alice\nhello world\nReply\nLike",
            "links": ["https://x.com/alice/status/99", "https://example.com/p"],
        }
    )
    assert item is not None
    assert item["author_handle"] == "alice"
    assert item["author_name"] == "Alice"
    assert item["tweet_text"] == "hello world"
    assert item["links"] == ["https://example.com/p"]
