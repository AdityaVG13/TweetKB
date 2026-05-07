from tweetkb.classifier import classify_text
from tweetkb.conversation import format_conversation_context, looks_like_question, should_capture_conversation


def test_detects_bookmarked_questions():
    assert looks_like_question("What are people using for local-first sync?")
    assert looks_like_question("Any recommendations for a browser automation library")
    assert not looks_like_question("Local-first sync patterns are useful")


def test_auto_conversation_capture_requires_question_and_context():
    payload = {
        "conversation_items": [
            {"role": "bookmarked", "text": "What vector DB should I use?"},
            {"role": "thread-or-reply", "text": "SQLite with vec extensions is enough for many apps."},
        ]
    }
    assert should_capture_conversation("What vector DB should I use?", payload=payload, mode="auto")
    assert not should_capture_conversation("SQLite is enough for many apps", payload=payload, mode="auto")
    assert should_capture_conversation("SQLite is enough for many apps", payload=payload, mode="always")
    assert not should_capture_conversation("What vector DB should I use?", payload=payload, mode="never")


def test_format_conversation_context_dedupes_and_labels_items():
    payload = {
        "conversation_items": [
            {
                "role": "bookmarked",
                "author_handle": "alice",
                "status_url": "https://x.com/alice/status/1",
                "text": "What should I use for evals?",
            },
            {
                "role": "thread-or-reply",
                "author_handle": "bob",
                "status_url": "https://x.com/bob/status/2",
                "text": "Start with a tiny golden dataset.",
            },
            {
                "role": "thread-or-reply",
                "author_handle": "bob",
                "status_url": "https://x.com/bob/status/2",
                "text": "Start with a tiny golden dataset.",
            },
        ]
    }
    text = format_conversation_context(payload)
    assert text.count("Start with a tiny golden dataset.") == 1
    assert "[bookmarked] @alice https://x.com/alice/status/1" in text
    assert "[thread-or-reply] @bob https://x.com/bob/status/2" in text


def test_question_classification_adds_question_context():
    result = classify_text("What tool should I use for browser automation and agents?", [])
    assert "question" in result["tags"]
    assert "thread and reply context" in result["why_it_matters"]
