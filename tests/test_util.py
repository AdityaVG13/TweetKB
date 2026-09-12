from __future__ import annotations

from tweetkb.util import extract_status_id, normalize_status_url, slugify, stable_hash


def test_extract_status_id_from_x_url():
    assert extract_status_id("https://x.com/alice/status/1234567890123456789") == "1234567890123456789"


def test_extract_status_id_from_twitter_url():
    assert extract_status_id("https://twitter.com/alice/status/123") == "123"


def test_extract_status_id_rejects_non_status_url():
    assert extract_status_id("https://x.com/alice") is None


def test_normalize_status_url_rewrites_twitter_host():
    assert (
        normalize_status_url("https://twitter.com/Alice/status/1", "alice", "1")
        == "https://x.com/alice/status/1"
    )


def test_slugify_falls_back_when_empty():
    assert slugify("???") == "bookmark"


def test_stable_hash_is_sha256_hex_and_stable():
    assert stable_hash("hello") == stable_hash("hello")
    assert stable_hash("hello") != stable_hash("Hello")
    assert len(stable_hash("hello")) == 64
