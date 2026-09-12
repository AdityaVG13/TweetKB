from __future__ import annotations

from tweetkb.classifier import classify_text
from tweetkb.pipeline import analyze_document


def test_analyze_document_matches_classify_text_without_a_database():
    text = "New browser agent automation workflow with MCP tool use"
    analysis = analyze_document(text, ())
    classified = classify_text(text, [])

    assert analysis.primary == classified["primary"] == "ai-agents"
    assert analysis.confidence == classified["confidence"]
    assert analysis.vector
    assert analysis.analysis_hash
    assert analysis.embed_provider == "local-hash"


def test_analyze_document_is_deterministic():
    text = "debugging a rust compiler borrow checker error in cargo test"
    first = analyze_document(text, ("https://github.com/rust-lang/rust",))
    second = analyze_document(text, ("https://github.com/rust-lang/rust",))
    assert first == second
