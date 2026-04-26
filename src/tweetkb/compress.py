from __future__ import annotations

import json
import struct
import zlib
from pathlib import Path
from typing import Any

MAGIC = b"TWZ1"
VERSION = 1


def _varint_encode(value: int) -> bytes:
    if value < 0:
        raise ValueError("Negative values not supported")
    result = bytearray()
    while value > 0x7F:
        result.append((value & 0x7F) | 0x80)
        value >>= 7
    result.append(value & 0x7F)
    return bytes(result)


def _varint_decode(data: bytes, pos: int) -> tuple[int, int]:
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
    """Encode records into TweetZip format.

    Layout:
        MAGIC(4) + VERSION(2) + FLAGS(2) = 8 bytes fixed header
        record_count (varint)
        string_count  (varint)
        body_size     (varint) -- byte size of encoded body
        dict_size     (varint) -- byte size of dictionary blob
        dict_blob     (N bytes) -- null-terminated strings
        body          (body_size bytes)
        checksum       (8 bytes)
    """
    if not records:
        return MAGIC + struct.pack("<HH", VERSION, 1)  # flag bit 0 = empty

    # Build string table
    all_strings: list[str] = []
    string_indices: dict[str, int] = {}

    STATIC_DICT = [
        "https://", "http://", "x.com/", "twitter.com/",
        "github.com/", "huggingface.co/", "arxiv.org/",
        "openai.com/", "anthropic.com/",
    ]
    for s in STATIC_DICT:
        if s not in string_indices:
            string_indices[s] = len(all_strings)
            all_strings.append(s)

    def get_field(record: dict, *keys: str) -> str:
        for key in keys:
            val = record.get(key)
            if val:
                return str(val)
        return ""

    # Collect strings from records
    for record in records:
        for val in (
            get_field(record, "id", "status_id"),
            get_field(record, "text", "tweet_text"),
            get_field(record, "url", "status_url"),
            get_field(record, "author", "author_handle"),
            get_field(record, "author_name"),
        ):
            if val and val not in string_indices:
                string_indices[val] = len(all_strings)
                all_strings.append(val)

    # Encode body
    body = bytearray()
    prev_id = 0
    for record in records:
        id_str = get_field(record, "id", "status_id")
        id_int = int(id_str) if id_str.isdigit() else 0
        body.extend(_varint_encode(id_int - prev_id))
        prev_id = id_int

        text = get_field(record, "text", "tweet_text")
        author = get_field(record, "author", "author_handle")
        url = get_field(record, "url", "status_url")
        mask = (1 if text else 0) | (2 if author else 0) | (4 if url else 0)
        body.extend(_varint_encode(mask))

        for val, bit in [(text, 1), (author, 2), (url, 4)]:
            if not (mask & bit):
                continue
            if val in string_indices:
                body.extend(_varint_encode(0))   # length=0 means ref
                body.extend(_varint_encode(string_indices[val]))
            else:
                bval = val.encode("utf-8")
                body.extend(_varint_encode(len(bval)))
                body.extend(bval)

    body_bytes = bytes(body)
    body_size = len(body_bytes)
    dict_blob = b"".join(s.encode("utf-8") + b"\x00" for s in all_strings)
    dict_size = len(dict_blob)
    checksum = zlib.crc32(body_bytes) & 0xFFFFFFFF

    # Assemble: fixed header (8) + varints + dict_blob + body + checksum
    result = bytearray()
    result.extend(MAGIC)                          # 4 bytes
    result.extend(struct.pack("<HH", VERSION, 0)) # 4 bytes
    result.extend(_varint_encode(len(records)))    # 1+ bytes
    result.extend(_varint_encode(len(all_strings)))
    result.extend(_varint_encode(body_size))
    result.extend(_varint_encode(dict_size))
    result.extend(dict_blob)
    result.extend(body_bytes)
    result.extend(struct.pack("<Q", checksum))
    return bytes(result)


def decode_records(data: bytes) -> list[dict]:
    """Decode TweetZip data back into records."""
    if len(data) < 8:
        raise ValueError("Data too short")
    if data[:4] != MAGIC:
        raise ValueError(f"Invalid magic: {data[:4]!r}")

    # Fixed header: MAGIC(4) + VERSION(2) + FLAGS(2) = 8 bytes
    flags = struct.unpack("<H", data[6:8])[0]
    pos = 8

    if flags & 1:  # empty records flag
        return []


    record_count, pos = _varint_decode(data, pos)
    string_count, pos = _varint_decode(data, pos)
    body_size, pos = _varint_decode(data, pos)
    dict_size, pos = _varint_decode(data, pos)

    # Parse dictionary
    dict_blob = data[pos : pos + dict_size]
    strings = [s.decode("utf-8") for s in dict_blob.split(b"\x00") if s]
    pos += dict_size

    # Body and checksum
    body = data[pos : pos + body_size]
    pos += body_size
    stored_crc = struct.unpack("<Q", data[pos : pos + 8])[0]
    computed_crc = zlib.crc32(body) & 0xFFFFFFFF
    if computed_crc != stored_crc:
        raise ValueError(f"Checksum mismatch: {computed_crc:#x} != {stored_crc:#x}")

    # Decode records
    records: list[dict[str, Any]] = []
    rpos = 0
    prev_id = 0
    for _ in range(record_count):
        delta, rpos = _varint_decode(body, rpos)
        id_val = prev_id + delta
        prev_id = id_val
        mask, rpos = _varint_decode(body, rpos)

        record: dict[str, Any] = {"id": id_val, "status_id": str(id_val)}
        for key, bit, out_key in [("text", 1, "text"), ("author", 2, "author"), ("url", 4, "url")]:
            if not (mask & bit):
                continue
            length, rpos = _varint_decode(body, rpos)
            if length == 0:
                idx, rpos = _varint_decode(body, rpos)
                record[out_key] = strings[idx] if idx < len(strings) else ""
            else:
                record[out_key] = body[rpos : rpos + length].decode("utf-8")
                rpos += length

        # Aliases
        if "text" in record:
            record["tweet_text"] = record["text"]
        if "url" in record:
            record["status_url"] = record["url"]
        if "author" in record:
            record["author_handle"] = record["author"]

        records.append(record)

    return records


def inspect_archive(data: bytes) -> dict:
    """Inspect a TweetZip archive without full decode."""
    if len(data) < 8:
        raise ValueError("Data too short")
    if data[:4] != MAGIC:
        raise ValueError("Invalid magic")
    flags = struct.unpack("<H", data[6:8])[0]
    if flags & 1:
        return {"magic": "TWZ1", "version": VERSION, "record_count": 0, "is_empty": True, "total_size": len(data)}
    pos = 8
    record_count, _ = _varint_decode(data, pos)
    string_count, pos = _varint_decode(data, pos)
    body_size, pos = _varint_decode(data, pos)
    dict_size, _ = _varint_decode(data, pos)
    return {
        "magic": "TWZ1",
        "version": VERSION,
        "record_count": record_count,
        "string_count": string_count,
        "body_size": body_size,
        "dict_size": dict_size,
        "total_size": len(data),
    }


def encode_file(input_path: Path, output_path: Path) -> None:
    records = []
    with input_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    output_path.write_bytes(encode_records(records))


def decode_file(input_path: Path, output_path: Path) -> None:
    records = decode_records(input_path.read_bytes())
    with output_path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def verify_archive(path: Path) -> bool:
    try:
        decode_records(path.read_bytes())
        return True
    except Exception:
        return False
