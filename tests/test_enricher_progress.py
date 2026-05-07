from tweetkb.enricher import enrich_with_apple_events


def test_enrich_reports_empty_selection_progress():
    messages: list[str] = []

    result = enrich_with_apple_events(None, [], progress=messages.append)

    assert result.enriched == 0
    assert messages == ["enrich: selected=0 include_links=False include_conversation=auto"]
