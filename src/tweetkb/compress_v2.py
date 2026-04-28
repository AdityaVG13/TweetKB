"""
TweetZip V2: Adaptive Differential Grammar with Learned Prediction (ADGLP)

V2 focuses on:
1. Corpus-aware URL grammar induction
2. Field-specific prediction chains
3. Semantic clustering with reference encoding

This is NOT claiming to be unprecedented research. It's a solid engineering
combination of known techniques applied specifically to bookmark corpus compression.
"""

from __future__ import annotations

import re
import struct
import zlib
from collections import Counter, defaultdict
from typing import Any

MAGIC = b"TWZ2"
VERSION = 2

# ─────────────────────────────────────────────────────────────────────────────
# UTILITY
# ─────────────────────────────────────────────────────────────────────────────

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

def _zigzag_encode(n: int) -> int:
    return (n << 1) ^ (n >> 31)

def _zigzag_decode(n: int) -> int:
    return (n >> 1) ^ -(n & 1)


# ─────────────────────────────────────────────────────────────────────────────
# URL GRAMMAR INDUCTION
# ─────────────────────────────────────────────────────────────────────────────

class URLGrammarInducer:
    """Learn URL structure from corpus for compact encoding."""

    def __init__(self):
        self.templates: list[tuple] = []
        self.template_map: dict[tuple, int] = {}

    def _segment_url(self, url: str) -> tuple[tuple, tuple]:
        """Segment URL into normalized pattern + raw components."""
        if not url or "://" not in url:
            return (), ()

        scheme_end = url.index("://")
        scheme = url[:scheme_end]
        rest = url[scheme_end + 3:]

        slash_pos = rest.find("/")
        if slash_pos >= 0:
            domain = rest[:slash_pos]
            path = rest[slash_pos + 1:]
        else:
            domain = rest
            path = ""

        path_parts = path.split("/") if path else []

        # Pattern: (base, segment1, segment2, ...) where base = scheme://domain
        base = f"{scheme}://{domain}"
        pattern_parts = [base]
        for p in path_parts:
            if p.isdigit():
                pattern_parts.append("{NUM}")
            elif re.match(r'^[a-zA-Z0-9_-]+$', p):
                pattern_parts.append("{TOKEN}")
            else:
                pattern_parts.append(p)

        pattern = tuple(pattern_parts)
        # Parts: (base, path1, path2, ...)
        parts = (base,) + tuple(path_parts)

        return pattern, parts

    def train(self, urls: list[str]) -> None:
        pattern_counts: Counter[tuple] = Counter()
        for url in urls:
            if not url:
                continue
            pattern, _ = self._segment_url(url)
            if pattern:
                pattern_counts[pattern] += 1

        sorted_patterns = sorted(pattern_counts.items(), key=lambda x: -x[1])[:32]
        self.template_map = {p: i for i, (p, _) in enumerate(sorted_patterns)}
        self.templates = [p for p, _ in sorted_patterns]

    def encode(self, url: str) -> bytes:
        """Encode URL using learned grammar. Returns (template_id, path_components)."""
        if not url:
            return b"\xff"  # Empty URL marker

        pattern, parts = self._segment_url(url)

        if pattern in self.template_map and len(pattern) > 1:
            template_id = self.template_map[pattern]
            result = bytearray()
            result.append(template_id)

            # Encode each path component: pattern[1:] = tokens, parts[1:] = values
            tokens = pattern[1:]
            values = parts[1:]
            for token, value in zip(tokens, values):
                if token == "{NUM}" or value.isdigit():
                    result.append(0x01)
                    val_bytes = str(value).encode("utf-8")
                    result.extend(_varint_encode(len(val_bytes)))
                    result.extend(val_bytes)
                elif token == "{TOKEN}" or re.match(r'^[a-zA-Z0-9_-]+$', value):
                    result.append(0x02)
                    val_bytes = str(value).encode("utf-8")
                    result.extend(_varint_encode(len(val_bytes)))
                    result.extend(val_bytes)
                else:
                    result.append(0x03)
                    val_bytes = str(value).encode("utf-8")
                    result.extend(_varint_encode(len(val_bytes)))
                    result.extend(val_bytes)

            return bytes(result)
        else:
            # No pattern match - raw URL
            raw = url.encode("utf-8")
            result = bytearray()
            result.append(0x80)
            result.extend(_varint_encode(len(raw)))
            result.extend(raw)
            return bytes(result)

    def decode(self, encoded: bytes) -> str:
        """Decode URL from grammar-encoded form."""
        if not encoded:
            return ""

        marker = encoded[0]
        pos = 1

        if marker == 0x80:
            length, pos = _varint_decode(encoded, pos)
            return encoded[pos:pos+length].decode("utf-8", errors="replace")

        if marker == 0xff:
            return ""

        if marker < 0x80 and marker < len(self.templates):
            pattern = self.templates[marker]
            if not pattern or len(pattern) < 1:
                return ""

            # Reconstruct: base + "/" + each decoded path component
            result = pattern[0]

            # Decode each path component from encoded data
            for token in pattern[1:]:
                if pos >= len(encoded):
                    break
                pos += 1
                length, pos = _varint_decode(encoded, pos)
                value = encoded[pos:pos+length].decode("utf-8", errors="replace")
                pos += length
                result += "/" + value

            return result

        return ""


# ─────────────────────────────────────────────────────────────────────────────
# BPE TOKENIZER
# ─────────────────────────────────────────────────────────────────────────────

class SimpleBPE:
    """Trainable Byte-Pair Encoding tokenizer."""

    def __init__(self, max_rules: int = 128):
        self.max_rules = max_rules
        self.merge_rules: list[tuple[bytes, bytes]] = []

    def train(self, texts: list[str]) -> None:
        """Train BPE on corpus."""
        pair_counts: Counter[tuple[int, int]] = Counter()

        for text in texts:
            if not text or len(text) < 2:
                continue
            chars = list(text.encode("utf-8"))
            for i in range(len(chars) - 1):
                pair_counts[(chars[i], chars[i+1])] += 1

        # Top N merge rules
        sorted_pairs = sorted(pair_counts.items(), key=lambda x: -x[1])
        self.merge_rules = [(bytes([p[0]]), bytes([p[1]])) for p, _ in sorted_pairs[:self.max_rules]]

    def encode(self, text: str) -> bytes:
        """Encode text using BPE. Returns (encoded_bytes, saved_bytes)."""
        if not text:
            return b"", 0

        original = text.encode("utf-8")
        if len(original) == 0:
            return b"", 0

        # Apply merge rules
        chars = list(original)
        tokens = [[b] for b in chars]

        for merge_a, merge_b in self.merge_rules:
            a, b = list(merge_a), list(merge_b)
            i = 0
            while i < len(tokens):
                if tokens[i] == a and i + 1 < len(tokens) and tokens[i+1] == b:
                    tokens[i] = a + b
                    del tokens[i + 1]
                else:
                    i += 1

        # Encode as: token_length (varint) + raw_bytes for each token
        result = bytearray()
        for token in tokens:
            result.extend(_varint_encode(len(token)))
            result.extend(bytes(token))

        encoded_size = len(result)
        saved = len(original) - encoded_size
        return bytes(result), saved

    def decode(self, encoded: bytes) -> str:
        """Decode BPE-encoded text."""
        if not encoded:
            return ""

        tokens = []
        pos = 0
        while pos < len(encoded):
            length, pos = _varint_decode(encoded, pos)
            token = encoded[pos:pos+length]
            pos += length
            tokens.append(token)

        return b"".join(tokens).decode("utf-8", errors="replace")


# ─────────────────────────────────────────────────────────────────────────────
# SEMANTIC CLUSTERING
# ─────────────────────────────────────────────────────────────────────────────

class SemanticClusterer:
    """Group records by semantic similarity for reference encoding."""

    def __init__(self):
        self.clusters: list[list[int]] = []
        self.cluster_of: dict[int, int] = {}  # record_idx -> cluster_idx

    def fit(self, records: list[dict]) -> None:
        """Cluster records by author and URL prefix."""
        author_groups: dict[str, list[int]] = defaultdict(list)
        url_prefix_groups: dict[str, list[int]] = defaultdict(list)

        for i, record in enumerate(records):
            author = str(record.get("author_handle", "") or record.get("author", "") or "")
            url = str(record.get("status_url", "") or record.get("url", "") or "")

            if author:
                author_groups[author].append(i)
            if url and "/" in url:
                parts = url.split("/")
                if len(parts) >= 4:
                    prefix = "/".join(parts[:4])
                    url_prefix_groups[prefix].append(i)

        self.clusters = []
        for indices in list(author_groups.values()) + list(url_prefix_groups.values()):
            if len(indices) >= 2:
                self.clusters.append(indices)
                for idx in indices:
                    self.cluster_of[idx] = len(self.clusters) - 1

    def get_cluster(self, idx: int) -> tuple[int | None, list[int]]:
        """Get cluster info for record idx. Returns (head_idx, other_indices)."""
        if idx not in self.cluster_of:
            return None, []
        cidx = self.cluster_of[idx]
        cluster = self.clusters[cidx]
        return cluster[0], [i for i in cluster if i != cluster[0]]


# ─────────────────────────────────────────────────────────────────────────────
# V2 MAIN ENCODER
# ─────────────────────────────────────────────────────────────────────────────

def encode_records_v2(records: list[dict]) -> bytes:
    """Encode records using V2 ADGLP compression.

    Layout:
        MAGIC(4) + VERSION(2) + FLAGS(2) = 8 bytes
        record_count (varint)
        ---- Grammar Section ----
        url_template_count (varint)
        url_templates_blob
        bpe_rule_count (varint)
        bpe_rules_blob
        ---- Cluster Section ----
        cluster_count (varint)
        cluster_data_blob
        ---- Records Section ----
        encoded_records (with prediction residuals)
        ---- Footer ----
        CRC32(4)
    """
    if not records:
        return MAGIC + struct.pack("<HH", VERSION, 1)

    # ── Train components ──
    urls = [str(r.get("status_url", "") or r.get("url", "") or "") for r in records]
    texts = [str(r.get("tweet_text", "") or r.get("text", "") or "") for r in records]

    url_grammar = URLGrammarInducer()
    url_grammar.train(urls)

    bpe = SimpleBPE(max_rules=64)
    bpe.train(texts)

    clusterer = SemanticClusterer()
    clusterer.fit(records)

    # ── Encode grammar section ──
    grammar_section = bytearray()

    # URL templates
    grammar_section.extend(_varint_encode(len(url_grammar.templates)))
    for template in url_grammar.templates:
        template_str = "\x1f".join(str(p) for p in template).encode("utf-8")
        grammar_section.extend(_varint_encode(len(template_str)))
        grammar_section.extend(template_str)

    # BPE rules
    grammar_section.extend(_varint_encode(len(bpe.merge_rules)))
    for merge_a, merge_b in bpe.merge_rules:
        grammar_section.append(len(merge_a))
        grammar_section.extend(merge_a)
        grammar_section.append(len(merge_b))
        grammar_section.extend(merge_b)

    grammar_bytes = bytes(grammar_section)

    # ── Encode records section ──
    records_section = bytearray()
    prev_id = 0
    prev_author = ""

    for i, record in enumerate(records):
        author = str(record.get("author_handle", "") or record.get("author", "") or "")
        url = str(record.get("status_url", "") or record.get("url", "") or "")
        text = str(record.get("tweet_text", "") or record.get("text", "") or "")
        id_str = str(record.get("status_id", "") or record.get("id", "") or "0")
        id_val = int(id_str) if id_str.isdigit() else 0

        # Cluster marker
        cluster_head, cluster_members = clusterer.get_cluster(i)
        is_head = cluster_head == i

        if is_head and cluster_members:
            records_section.append(0x80 | min(len(cluster_members), 0x7F))
        else:
            records_section.append(0x00)

        # ID delta
        delta = id_val - prev_id
        records_section.extend(_varint_encode(_zigzag_encode(delta)))
        prev_id = id_val

        # Author prediction
        if author == prev_author:
            records_section.append(0x01)  # Same as previous
        elif author:
            author_bytes = author.encode("utf-8")
            records_section.append(0x02)  # New author
            records_section.extend(_varint_encode(len(author_bytes)))
            records_section.extend(author_bytes)
        else:
            records_section.append(0x00)  # No author
        prev_author = author

        # URL grammar encoding
        encoded_url = url_grammar.encode(url)
        if len(encoded_url) < len(url.encode("utf-8")):
            records_section.extend(b"\x01")  # Grammar encoded
            records_section.extend(_varint_encode(len(encoded_url)))
            records_section.extend(encoded_url)
        else:
            records_section.extend(b"\x00")  # Raw
            raw_bytes = url.encode("utf-8")
            records_section.extend(_varint_encode(len(raw_bytes)))
            records_section.extend(raw_bytes)

        # Text BPE encoding
        encoded_text, saved = bpe.encode(text)
        if saved > 0:
            records_section.extend(b"\x01")  # BPE encoded
            records_section.extend(_varint_encode(len(encoded_text)))
            records_section.extend(encoded_text)
        else:
            records_section.extend(b"\x00")  # Raw
            raw_bytes = text.encode("utf-8")
            records_section.extend(_varint_encode(len(raw_bytes)))
            records_section.extend(raw_bytes)

    records_bytes = bytes(records_section)

    # ── Encode cluster section ──
    cluster_section = bytearray()
    cluster_section.extend(_varint_encode(len(clusterer.clusters)))
    for cluster in clusterer.clusters:
        cluster_section.extend(_varint_encode(len(cluster)))
        cluster_section.extend(_varint_encode(cluster[0]))  # head
        for idx in cluster[1:]:
            cluster_section.extend(_varint_encode(idx))
    cluster_bytes = bytes(cluster_section)

    # ── Assemble container ──
    checksum_data = grammar_bytes + cluster_bytes + records_bytes
    checksum = zlib.crc32(checksum_data) & 0xFFFFFFFF

    result = bytearray()
    result.extend(MAGIC)
    result.extend(struct.pack("<HH", VERSION, 0))
    result.extend(_varint_encode(len(records)))
    result.extend(_varint_encode(len(grammar_bytes)))
    result.extend(_varint_encode(len(cluster_bytes)))
    result.extend(grammar_bytes)
    result.extend(cluster_bytes)
    result.extend(records_bytes)
    result.extend(struct.pack("<I", checksum))

    return bytes(result)


def decode_records_v2(data: bytes) -> list[dict]:
    """Decode V2 compressed records."""
    if len(data) < 8:
        raise ValueError("Data too short")
    if data[:4] != MAGIC:
        raise ValueError(f"Invalid magic: {data[:4]!r}")

    flags = struct.unpack("<H", data[6:8])[0]
    if flags & 1:
        return []

    pos = 8
    record_count, pos = _varint_decode(data, pos)
    grammar_size, pos = _varint_decode(data, pos)
    cluster_size, pos = _varint_decode(data, pos)

    grammar_end = pos + grammar_size
    grammar_data = data[pos:grammar_end]
    pos = grammar_end

    # Decode grammar
    gp = 0
    url_template_count, gp = _varint_decode(grammar_data, gp)
    url_templates = []
    for _ in range(url_template_count):
        length, gp = _varint_decode(grammar_data, gp)
        template_bytes = grammar_data[gp:gp+length]
        gp += length
        template = tuple(template_bytes.decode("utf-8").split("\x1f"))
        url_templates.append(template)

    bpe_count, gp = _varint_decode(grammar_data, gp)
    bpe_rules = []
    for _ in range(min(bpe_count, 128)):
        if gp >= len(grammar_data):
            break
        alen = grammar_data[gp]
        gp += 1
        a = grammar_data[gp:gp+alen]
        gp += alen
        blen = grammar_data[gp]
        gp += 1
        b = grammar_data[gp:gp+blen]
        gp += blen
        bpe_rules.append((a, b))

    # Reconstruct URL grammar
    url_grammar = URLGrammarInducer()
    url_grammar.templates = url_templates
    url_grammar.template_map = {t: i for i, t in enumerate(url_templates)}

    # Reconstruct BPE
    bpe = SimpleBPE(max_rules=128)
    bpe.merge_rules = bpe_rules

    # Decode clusters
    cluster_end = pos + cluster_size
    cluster_data = data[pos:cluster_end]
    cp = 0
    cluster_count, cp = _varint_decode(cluster_data, cp)
    clusters = []
    for _ in range(cluster_count):
        size, cp = _varint_decode(cluster_data, cp)
        head, cp = _varint_decode(cluster_data, cp)
        members = [head]
        for _ in range(size - 1):
            idx, cp = _varint_decode(cluster_data, cp)
            members.append(idx)
        clusters.append(members)
    pos = cluster_end

    # Verify checksum
    records_start = pos
    records_end = len(data) - 4
    records_data = data[records_start:records_end]
    stored_crc = struct.unpack("<I", data[records_end:])[0]
    computed_crc = zlib.crc32(grammar_data + cluster_data + records_data) & 0xFFFFFFFF
    if computed_crc != stored_crc:
        raise ValueError(f"Checksum mismatch: stored={stored_crc:#x}, computed={computed_crc:#x}")

    # Decode records
    records: list[dict[str, Any]] = []
    rp = 0
    prev_id = 0
    prev_author = ""

    for i in range(record_count):
        if rp >= len(records_data):
            break

        record: dict[str, Any] = {}

        # Cluster marker
        cluster_marker = records_data[rp]
        rp += 1
        bool(cluster_marker & 0x80)
        cluster_marker & 0x7F

        # ID
        delta, rp = _varint_decode(records_data, rp)
        id_val = prev_id + _zigzag_decode(delta)
        prev_id = id_val
        record["id"] = id_val
        record["status_id"] = str(id_val)

        # Author
        if rp >= len(records_data):
            break
        author_marker = records_data[rp]
        rp += 1
        if author_marker == 0x01:
            record["author"] = prev_author
        elif author_marker == 0x02:
            length, rp = _varint_decode(records_data, rp)
            author = records_data[rp:rp+length].decode("utf-8", errors="replace")
            rp += length
            record["author"] = author
            prev_author = author
        else:
            record["author"] = ""
        record["author_handle"] = record["author"]

        # URL
        if rp >= len(records_data):
            break
        url_marker = records_data[rp]
        rp += 1
        length, rp = _varint_decode(records_data, rp)
        url_data = records_data[rp:rp+length]
        rp += length

        if url_marker == 0x00:
            record["url"] = url_data.decode("utf-8", errors="replace")
        else:
            record["url"] = url_grammar.decode(url_data)
        record["status_url"] = record["url"]

        # Text
        if rp >= len(records_data):
            break
        text_marker = records_data[rp]
        rp += 1
        length, rp = _varint_decode(records_data, rp)
        text_data = records_data[rp:rp+length]
        rp += length

        if text_marker == 0x00:
            record["text"] = text_data.decode("utf-8", errors="replace")
        else:
            record["text"] = bpe.decode(text_data)
        record["tweet_text"] = record["text"]

        records.append(record)

    return records


def inspect_archive_v2(data: bytes) -> dict:
    """Inspect V2 archive without full decode."""
    if len(data) < 8:
        raise ValueError("Data too short")
    if data[:4] != MAGIC:
        raise ValueError("Invalid magic")
    flags = struct.unpack("<H", data[6:8])[0]
    if flags & 1:
        return {"magic": "TWZ2", "version": VERSION, "record_count": 0, "is_empty": True}

    pos = 8
    record_count, pos = _varint_decode(data, pos)
    grammar_size, pos = _varint_decode(data, pos)
    cluster_size, pos = _varint_decode(data, pos)

    return {
        "magic": "TWZ2",
        "version": VERSION,
        "record_count": record_count,
        "grammar_size": grammar_size,
        "cluster_size": cluster_size,
        "total_size": len(data),
    }
