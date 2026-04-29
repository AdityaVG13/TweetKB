from tweetkb.enricher import _candidate_outbound_links


def test_candidate_outbound_links_skips_x_help_and_cookie_links():
    links = [
        {"url": "https://help.x.com/en/rules-and-policies/x-cookies", "text": "Cookies", "aria": ""},
        {"url": "https://business.x.com/en/help/troubleshooting/how-x-ads-work", "text": "Ads help", "aria": ""},
        {"url": "https://example.com/article", "text": "Read the full article", "aria": ""},
    ]

    assert _candidate_outbound_links(links, max_links=5) == ["https://example.com/article"]


def test_candidate_outbound_links_skips_policy_anchor_text():
    links = [
        {"url": "https://example.com/privacy", "text": "Privacy policy", "aria": ""},
        {"url": "https://docs.example.com/guide", "text": "Implementation guide", "aria": ""},
    ]

    assert _candidate_outbound_links(links, max_links=5) == ["https://docs.example.com/guide"]
