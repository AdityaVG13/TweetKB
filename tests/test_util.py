from tweetkb.util import extract_status_id, normalize_status_url, slugify


def test_extract_status_id_from_x_url():
    assert extract_status_id("https://x.com/aditya/status/123456789?s=20") == "123456789"


def test_extract_status_id_from_twitter_url():
    assert extract_status_id("https://twitter.com/foo/status/42") == "42"


def test_normalize_status_url():
    assert normalize_status_url("https://twitter.com/foo/status/42?s=20", "@bar") == "https://x.com/bar/status/42"


def test_slugify_has_fallback():
    assert slugify("!!!", fallback="x") == "x"

