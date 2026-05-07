from tweetkb.enricher import _candidate_outbound_links, enrich_with_apple_events


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


def test_enrich_stores_conversation_for_question(monkeypatch):
    payload = {
        "url": "https://x.com/a/status/1",
        "source_type": "x-status",
        "content_text": "What eval harness should I use?",
        "conversation_items": [
            {
                "role": "bookmarked",
                "author_handle": "a",
                "status_url": "https://x.com/a/status/1",
                "text": "What eval harness should I use?",
            },
            {
                "role": "thread-or-reply",
                "author_handle": "b",
                "status_url": "https://x.com/b/status/2",
                "text": "Use a small golden set first.",
            },
        ],
    }
    calls = []

    class FakeStore:
        def set_content_enrichment(self, **kwargs):
            calls.append(kwargs)
            return True

    monkeypatch.setattr("tweetkb.enricher.capture_x_content_with_apple_events", lambda *args, **kwargs: payload)
    result = enrich_with_apple_events(
        FakeStore(),
        [{"id": 1, "status_url": "https://x.com/a/status/1", "tweet_text": "What eval harness should I use?", "raw_text": ""}],
    )
    assert result.enriched == 1
    assert result.conversations == 1
    assert calls[1]["source_type"] == "x-conversation"
    assert "Use a small golden set first." in calls[1]["content_text"]
