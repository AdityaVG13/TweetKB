from __future__ import annotations

import json
import struct
import zlib
from pathlib import Path
from typing import Any

MAGIC = b"TWZ1"
VERSION = 1


def _varint_encode(value: int) -> bytes:
    """Encode an integer as a variable-length byte sequence."""
    if value < 0:
        raise ValueError("Negative values not supported")
    result = bytearray()
    while value > 0x7F:
        result.append((value & 0x7F) | 0x80)
        value >>= 7
    result.append(value & 0x7F)
    return bytes(result)


def _varint_decode(data: bytes, pos: int) -> tuple[int, int]:
    """Decode a varint. Returns (value, new_position)."""
    value = 0
    shift = 0
    while True:
        b = data[pos]
        value |= (b & 0x7F) << shift
        pos += 1
        if not (b & 0x80):
            break
        shift += 7
    return value, pos


def encode_records(records: list[dict]) -> bytes:
    """Encode a list of bookmark records into TweetZip format."""
    if not records:
        return MAGIC + struct.pack("<H", VERSION) + _varint_encode(0)

    # Build dictionary of common strings
    all_strings: list[str] = []
    string_indices: dict[str, int] = {}

    STATIC_DICT = [
        "https://", "http://", "x.com/", "twitter.com/",
        "github.com/", "huggingface.co/", "arxiv.org/",
        "openai.com/", "anthropic.com/",
    ]
    for s in STATIC_DICT:
        if s not in string_indices:
            idx = len(all_strings)
            string_indices[s] = idx
            all_strings.append(s)

    # Extract all string values from records
    for record in records:
        for key in ("status_id", "author_handle", "author_name", "tweet_text", "status_url"):
            val = record.get(key, "")
            if val and val not in string_indices:
                string_indices[val] = len(all_strings)
                all_strings.append(val)

    # Build dictionary blob
    dict_blob = b"".join(s.encode("utf-8") + b"\x00" for s in all_strings)

    # Encode records
    encoded_records = bytearray()
    prev_status_id = 0

    for record in records:
        status_id_str = record.get("status_id", "")
        status_id_int = int(status_id_str) if status_id_str.isdigit() else 0

        # Delta encode status ID
        delta = status_id_int - prev_status_id
        encoded_records.extend(_varint_encode(delta))
        prev_status_id = status_id_int

        # Field mask (which fields are present)
        fields = []
        text = record.get("tweet_text", "")
        author = record.get("author_handle", "")
        url = record.get("status_url", "")

        if text:
            fields.append("text")
        if author:
            fields.append("author")
        if url:
            fields.append("url")

        field_mask = 0
        if "text" in fields:
            field_mask |= 1
        if "author" in fields:
            field_mask |= 2
        if "url" in fields:
            field_mask |= 4
        encoded_records.extend(_varint_encode(field_mask))

        # Encode each field as string table reference or inline
        for field_name in ("text", "author", "url"):
            if field_name not in fields:
                continue
            value = record.get(field_name, "")
            if value in string_indices:
                # Reference to string table (high bit set)
                ref = string_indices[value] | 0x8000
                encoded_records.extend(struct.pack("<H", ref))
            else:
                # Inline string (length prefix)
                bvalue = value.encode("utf-8")
                encoded_records.extend(_varint_encode(len(bvalue)))
                encoded_records.extend(bvalue)

    # Build final container
    flags = 0
    header = MAGIC + struct.pack("<H", flags)
    header += _varint_encode(len(records))
    header += _varint_encode(len(all_strings))
    header += struct.pack("<Q", len(dict_blob))
    header += dict_blob

    body = bytes(encoded_records)
    checksum = zlib.crc32(body) & 0xFFFFFFFF

    return header + body + struct.pack("<Q", checksum)


def decode_records(data: bytes) -> list[dict]:
    """Decode TweetZip data back into records."""
    if len(data) < len(MAGIC) + 2:
        raise ValueError("Data too short")

    magic = data[:4]
    if magic != MAGIC:
        raise ValueError(f"Invalid magic: {magic!r}")

    version = struct.unpack("<H", data[4:6])[0]
    pos = 6

    record_count, pos = _varint_decode(data, pos)
    dict_len, pos = _varint_decode(data, pos)
    dict_size, pos = _varint_decode(data, pos)

    dict_blob = data[pos : pos + dict_size]
    pos += dict_size

    # Parse dictionary
    strings = []
    for part in dict_blob.split(b"\x00"):
        if part:
            strings.append(part.decode("utf-8"))

    body_start = pos
    body_end = len(data) - 8
    body = data[body_start:body_end]
    stored_checksum = struct.unpack("<Q", data[body_end:])[0]
    computed_checksum = zlib.crc32(body) & 0xFFFFFFFF

    if computed_checksum != stored_checksum:
        raise ValueError(f"Checksum mismatch: {computed_checksum:#x} != {stored_checksum:#x}")

    # Decode records
    records = []
    pos = 0
    prev_status_id = 0

    for _ in range(record_count):
        delta, pos = _varint_decode(data, pos)
        status_id = prev_status_id + delta
        prev_status_id = status_id

        field_mask, pos = _varint_decode(data, pos)

        record: dict[str, Any] = {"status_id": str(status_id)}

        for field_name, mask_bit in [("text", 1), ("author", 2), ("url", 4)]:
            if not (field_mask & mask_bit):
                continue

            ref = struct.unpack("<H", data[pos : pos + 2])[0]
            pos += 2

            if ref & 0x8000:
                idx = ref & 0x7FFF
                if idx < len(strings):
                    record[field_name] = strings[idx]
            else:
                length, new_pos = _varint_decode(data, pos)
                pos = new_pos
                record[field_name] = data[pos : pos + length].decode("utf-8")
                pos += length

        records.append(record)

    return records


def inspect_archive(data: bytes) -> dict:
    """Inspect a TweetZip archive without decoding all records."""
    if len(data) < len(MAGIC) + 2:
        raise ValueError("Data too short")

    magic = data[:4]
    if magic != MAGIC:
        raise ValueError(f"Invalid magic: {magic!r}")

    pos = 6
    record_count, pos = _varint_decode(data, pos)
    dict_len, pos = _varint_decode(data, pos)
    dict_size, pos = _varint_decode(data, pos)

    return {
        "magic": MAGIC.decode(),
        "record_count": record_count,
        "dict_entries": dict_len,
        "dict_size_bytes": dict_size,
        "total_size_bytes": len(data),
        "compression_ratio": f"{len(data) / (record_count * 200 + 1):.2f}x" if record_count > 0 else "N/A",
    }


def encode_file(input_path: Path, output_path: Path) -> None:
    """Encode a JSONL file to TweetZip."""
    records = []
    with input_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    data = encode_records(records)
    output_path.write_bytes(data)


def decode_file(input_path: Path, output_path: Path) -> None:
    """Decode a TweetZip file to JSONL."""
    data = input_path.read_bytes()
    records = decode_records(data)
    with output_path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def verify_archive(path: Path) -> bool:
    """Verify a TweetZip archive. Returns True if valid."""
    try:
        data = path.read_bytes()
        decode_records(data)
        return True
    except Exception:
        return False
