from __future__ import annotations

from tweetkb.classifier import classify_text


def test_agent_mcp_workflow_classifies_as_ai_agents():
    result = classify_text("New browser agent automation workflow with MCP tool use", [])

    assert result["primary"] == "ai-agents"
    assert result["confidence"] > 0.5
    assert any(item["slug"] == "ai-agents" for item in result["categories"])


def test_rust_compiler_text_classifies_as_coding():
    result = classify_text("debugging a rust compiler borrow checker error in cargo test", [])

    assert result["primary"] == "coding"


def test_empty_text_is_misc_with_review_flag():
    result = classify_text("", [])

    assert result["primary"] == "misc"
    assert result["needs_review"] is True
