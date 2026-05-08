from __future__ import annotations

import json

from tweetkb.image_analysis import (
    _extract_openai_text,
    analyze_image_media,
    candidate_media_images,
)


def test_candidate_media_images_skips_avatars_and_deduplicates():
    media = [
        {"url": "https://pbs.twimg.com/profile_images/1/avatar.jpg", "alt": "avatar"},
        {"url": "https://pbs.twimg.com/media/abc.jpg?format=jpg&name=large", "alt": "diagram"},
        {"url": "https://pbs.twimg.com/media/abc.jpg?format=jpg&name=large", "alt": "diagram"},
        {"url": "https://example.com/picture.png", "alt": ""},
    ]

    assert candidate_media_images(media, max_media=5) == [
        {"url": "https://pbs.twimg.com/media/abc.jpg?format=jpg&name=large", "alt": "diagram"},
        {"url": "https://example.com/picture.png", "alt": ""},
    ]


def test_metadata_provider_returns_alt_text():
    result = analyze_image_media(
        {"url": "https://pbs.twimg.com/media/abc.jpg", "alt": "A screenshot of a benchmark table"},
        provider="metadata",
    )

    assert result.provider == "metadata"
    assert "benchmark table" in result.content_text


def test_extract_openai_text_from_responses_payload():
    payload = {
        "output": [
            {
                "content": [
                    {"type": "output_text", "text": "Visible text and chart summary."},
                ]
            }
        ]
    }

    assert _extract_openai_text(payload) == "Visible text and chart summary."


def test_openai_provider_posts_image_url(monkeypatch):
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self):
            return json.dumps({"output_text": "A UI screenshot with a pricing table."}).encode()

    def fake_urlopen(request, timeout):
        captured["body"] = json.loads(request.data.decode())
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr("tweetkb.image_analysis.urllib.request.urlopen", fake_urlopen)

    result = analyze_image_media(
        {"url": "https://pbs.twimg.com/media/abc.jpg", "alt": "pricing table"},
        provider="openai",
        model="gpt-test",
        detail="high",
        context_text="bookmarked post",
    )

    image_input = captured["body"]["input"][0]["content"][1]
    assert image_input == {
        "type": "input_image",
        "image_url": "https://pbs.twimg.com/media/abc.jpg",
        "detail": "high",
    }
    assert result.provider == "openai"
    assert "pricing table" in result.content_text
