from tweetkb.entities import extract_entities, detect_entity_type, get_domain, normalize_entity_name


def test_extract_entities_basic():
    """extract_entities finds entities in text."""
    text = "Amazon AWS Lambda serverless on Microsoft Azure"
    entities = extract_entities(text)
    assert len(entities) > 0
    names = {e[0] for e in entities}
    assert len(names) > 0


def test_extract_entities_empty():
    """extract_entities handles empty text."""
    entities = extract_entities("")
    assert entities == []


def test_detect_entity_type():
    """detect_entity_type returns a type string."""
    entity_type = detect_entity_type("test")
    assert isinstance(entity_type, str)
    assert entity_type


def test_get_domain():
    """get_domain extracts domain from URL."""
    domain = get_domain("https://example.com/path/to/page")
    assert domain == "example.com"


def test_normalize_entity_name():
    """normalize_entity_name normalizes entity names."""
    name = normalize_entity_name("  Test Entity  ")
    # Returns lowercase per implementation
    assert name == "test entity"
