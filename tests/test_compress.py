from pathlib import Path
from tweetkb.compress import encode_records, decode_records, verify_archive, encode_file, decode_file, inspect_archive, MAGIC


def test_magic_header():
    """Magic header is correct."""
    assert MAGIC == b"TWZ1"


def test_encode_decode_empty():
    """Encode and decode empty list."""
    encoded = encode_records([])
    assert encoded.startswith(MAGIC)
    decoded = decode_records(encoded)
    assert decoded == []


def test_encode_decode_single_record():
    """Encode and decode a single record."""
    records = [{"id": 1, "text": "hello world", "url": "https://example.com/1"}]
    encoded = encode_records(records)
    decoded = decode_records(encoded)
    assert len(decoded) == 1
    assert decoded[0]["id"] == 1
    assert decoded[0]["text"] == "hello world"
    assert decoded[0]["url"] == "https://example.com/1"


def test_encode_decode_roundtrip():
    """Encode and decode roundtrip preserves data."""
    records = [
        {"id": 1, "text": "hello world", "url": "https://example.com/1"},
        {"id": 2, "text": "foo bar", "url": "https://example.com/2"},
    ]
    encoded = encode_records(records)
    assert isinstance(encoded, bytes)
    decoded = decode_records(encoded)
    assert len(decoded) == 2
    assert decoded[0]["id"] == 1
    assert decoded[0]["text"] == "hello world"
    assert decoded[1]["id"] == 2
    assert decoded[1]["text"] == "foo bar"


def test_encode_decode_unicode():
    """Unicode roundtrip works."""
    records = [
        {"id": 1, "text": "Hello 世界 🌍 émoji", "url": "https://例え.jp/1"},
    ]
    encoded = encode_records(records)
    decoded = decode_records(encoded)
    assert decoded[0]["text"] == "Hello 世界 🌍 émoji"


def test_encode_decode_with_author():
    """Author field roundtrips correctly."""
    records = [
        {"id": 1, "text": "test", "url": "https://x.com/user/status/1", "author": "testuser"},
    ]
    encoded = encode_records(records)
    decoded = decode_records(encoded)
    assert decoded[0]["author"] == "testuser"


def test_encode_decode_delta_ids():
    """Status ID delta encoding works for sequential IDs."""
    records = [{"id": 100, "text": "a"}, {"id": 101, "text": "b"}, {"id": 102, "text": "c"}]
    encoded = encode_records(records)
    decoded = decode_records(encoded)
    assert [r["id"] for r in decoded] == [100, 101, 102]


def test_encode_decode_checksum_valid():
    """Checksum validation works on valid data."""
    records = [{"id": 1, "text": "test"}]
    encoded = encode_records(records)
    # Should not raise
    decode_records(encoded)


def test_encode_decode_corrupt_magic():
    """Corrupt magic header is rejected."""
    import pytest
    records = [{"id": 1, "text": "test"}]
    encoded = encode_records(records)
    corrupt = b"TWZZ" + encoded[4:]
    with pytest.raises(ValueError, match="Invalid magic"):
        decode_records(corrupt)


def test_inspect_archive():
    """inspect_archive returns metadata."""
    records = [{"id": 1, "text": "test"}, {"id": 2, "text": "test2"}]
    encoded = encode_records(records)
    info = inspect_archive(encoded)
    assert info["magic"] == "TWZ1"
    assert info["record_count"] == 2
    assert info["version"] == 1


def test_encode_file_roundtrip(tmp_path: Path):
    """Encode and decode file roundtrip preserves data."""
    records = [{"id": 1, "text": "test"}]
    input_path = tmp_path / "input.jsonl"
    output_path = tmp_path / "output.twz"
    decoded_path = tmp_path / "decoded.jsonl"

    # Create input file
    import json
    with open(input_path, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")

    # Encode
    encode_file(input_path, output_path)
    assert output_path.exists()

    # Verify
    assert verify_archive(output_path)

    # Decode
    decode_file(output_path, decoded_path)
    with open(decoded_path) as f:
        lines = f.readlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["text"] == "test"


def test_verify_archive_valid(tmp_path: Path):
    """verify_archive returns True for valid archive."""
    records = [{"id": 1, "text": "hello"}]
    encoded = encode_records(records)
    path = tmp_path / "test.twz"
    path.write_bytes(encoded)
    assert verify_archive(path)
