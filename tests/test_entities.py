from __future__ import annotations

from tweetkb.entities import detect_entity_type, extract_entities, get_domain, normalize_entity_name


def test_extract_entities_returns_named_cloud_products():
    entities = extract_entities("Amazon AWS Lambda serverless on Microsoft Azure")
    names = {name.lower() for name, _etype, _source in entities}

    assert any("azure" in name for name in names)
    assert any("lambda" in name or "aws" in name for name in names)


def test_github_repo_url_extracts_repo_entity():
    entities = extract_entities("see this", ["https://github.com/browser-use/browser-harness"])
    repos = [(name, etype) for name, etype, source in entities if etype == "repo"]

    assert repos
    assert any("browser-harness" in name or "browser-use" in name for name, _etype in repos)


def test_extract_entities_skips_english_glue_words():
    names = {name.lower() for name, _etype, _source in extract_entities("This is Rust. You can use MCP.")}
    assert "this" not in names
    assert "you" not in names
    assert "mcp" in names or "rust" in names


def test_empty_text_extracts_no_entities():
    assert extract_entities("") == []


def test_mcp_is_typed_as_protocol():
    assert detect_entity_type("MCP") == "protocol"


def test_get_domain_strips_www():
    assert get_domain("https://www.example.com/path/to/page") == "example.com"


def test_normalize_entity_name_strips_and_lowercases():
    assert normalize_entity_name("  Test Entity  ") == "test entity"
