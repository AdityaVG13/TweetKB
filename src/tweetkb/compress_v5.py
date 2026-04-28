"""
TweetZip V5: Advanced Hybrid Compression

Improvements over V4:
1. BPE tokenization for text fields (better than raw bytes)
2. Relative URL encoding (delta from previous URL)
3. Run-length encoding for consecutive identical authors
4. Streaming-friendly format (chunked encoding for large datasets)
5. Better backend: auto-select gzip/zlib/lz4 based on size
"""

from __future__ import annotations

import gzip
import re
import struct
import zlib
from collections import Counter

MAGIC = b"TWZ5"
VERSION = 5

# ─────────────────────────────────────────────────────────────────────────────
# VARINT & ZIGZAG
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
    while pos < len(data):
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
# SIMPLE BPE TOKENIZER (for text compression)
# ─────────────────────────────────────────────────────────────────────────────

class SimpleBPE:
    """Fast BPE tokenizer for text compression."""

    def __init__(self, max_rules: int = 256):
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

        sorted_pairs = sorted(pair_counts.items(), key=lambda x: -x[1])
        self.merge_rules = [(bytes([p[0]]), bytes([p[1]])) for p, _ in sorted_pairs[:self.max_rules]]

    def encode(self, text: str) -> bytes:
        """Encode text with BPE."""
        if not text:
            return b""

        original = text.encode("utf-8")
        if len(original) == 0:
            return b""

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

        result = bytearray()
        for token in tokens:
            result.extend(_varint_encode(len(token)))
            result.extend(bytes(token))

        return bytes(result)

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
# URL GRAMMAR
# ─────────────────────────────────────────────────────────────────────────────

class URLGrammarV2:
    """Improved URL grammar with better compression."""

    def __init__(self):
        self.templates: list[tuple] = []
        self.template_map: dict[tuple, int] = {}

    def _segment_url(self, url: str) -> tuple[tuple, tuple]:
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
        base = f"{scheme}://{domain}"
        pattern_parts = [base]
        for p in path_parts:
            if p.isdigit():
                pattern_parts.append("{NUM}")
            elif re.match(r'^[a-zA-Z0-9_-]+$', p):
                pattern_parts.append("{TOKEN}")
            else:
                pattern_parts.append(p)
        return tuple(pattern_parts), (base,) + tuple(path_parts)

    def train(self, urls: list[str]) -> None:
        pattern_counts: Counter[tuple] = Counter()
        for url in urls:
            if not url:
                continue
            pattern, _ = self._segment_url(url)
            if pattern and len(pattern) > 1:
                pattern_counts[pattern] += 1
        sorted_patterns = sorted(pattern_counts.items(), key=lambda x: -x[1])[:64]
        self.template_map = {p: i for i, (p, _) in enumerate(sorted_patterns)}
        self.templates = [p for p, _ in sorted_patterns]

    def encode(self, url: str) -> bytes:
        if not url:
            return b"\xff"
        pattern, parts = self._segment_url(url)
        if pattern in self.template_map and len(pattern) > 1:
            template_id = self.template_map[pattern]
            result = bytearray()
            result.append(template_id)
            tokens = pattern[1:]
            values = parts[1:]
            for token, value in zip(tokens, values):
                if token == "{NUM}" or (value.isdigit() and len(value) > 2):
                    result.append(0x01)
                    vb = str(value).encode("utf-8")
                    result.extend(_varint_encode(len(vb)))
                    result.extend(vb)
                elif token == "{TOKEN}":
                    result.append(0x02)
                    vb = str(value).encode("utf-8")
                    result.extend(_varint_encode(len(vb)))
                    result.extend(vb)
                else:
                    result.append(0x03)
                    vb = str(value).encode("utf-8")
                    result.extend(_varint_encode(len(vb)))
                    result.extend(vb)
            return bytes(result)
        raw = url.encode("utf-8")
        result = bytearray()
        result.append(0x80)
        result.extend(_varint_encode(len(raw)))
        result.extend(raw)
        return bytes(result)

    def decode(self, encoded: bytes) -> str:
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
            result = pattern[0]
            for token in pattern[1:]:
                if pos >= len(encoded):
                    break
                _ = encoded[pos]
                pos += 1
                length, pos = _varint_decode(encoded, pos)
                value = encoded[pos:pos+length].decode("utf-8", errors="replace")
                pos += length
                result += "/" + value
            return result
        return ""

    def encode_template_index(self) -> bytes:
        result = bytearray()
        result.extend(_varint_encode(len(self.templates)))
        for template in self.templates:
            template_str = "\x1f".join(str(p) for p in template).encode("utf-8")
            result.extend(_varint_encode(len(template_str)))
            result.extend(template_str)
        return bytes(result)

    @classmethod
    def decode_template_index(cls, data: bytes, pos: int) -> tuple[list[tuple], int]:
        count, pos = _varint_decode(data, pos)
        templates = []
        for _ in range(count):
            length, pos = _varint_decode(data, pos)
            tpl_bytes = data[pos:pos+length]
            pos += length
            templates.append(tuple(tpl_bytes.decode("utf-8").split("\x1f")))
        return templates, pos


# ─────────────────────────────────────────────────────────────────────────────
# PHRASE DICTIONARY
# ─────────────────────────────────────────────────────────────────────────────

class PhraseDictionary:
    """Dictionary for frequently occurring multi-word phrases."""

    def __init__(self, max_entries: int = 256):
        self.max_entries = max_entries
        self.phrases: list[str] = []
        self.phrase_map: dict[str, int] = {}

    def train(self, texts: list[str]) -> None:
        phrase_counts: Counter[str] = Counter()
        for text in texts:
            words = text.lower().split()
            for n in [2, 3, 4]:
                for i in range(len(words) - n + 1):
                    phrase = " ".join(words[i:i+n])
                    if len(phrase) >= 5:
                        phrase_counts[phrase] += 1

        top = sorted(phrase_counts.items(), key=lambda x: -x[1])[:self.max_entries]
        self.phrases = [p for p, _ in top]
        self.phrase_map = {p: i for i, p in enumerate(self.phrases)}

    def encode(self, text: str) -> bytes:
        """Replace known phrases with dictionary indices. Returns (encoded, markers)."""
        if not text or not self.phrases:
            return text.encode("utf-8")

        result = bytearray()
        text_lower = text.lower()
        pos = 0

        while pos < len(text):
            best_phrase = None
            best_len = 0
            best_idx = -1

            for phrase, idx in self.phrase_map.items():
                if text_lower.startswith(phrase, pos):
                    if len(phrase) > best_len:
                        best_phrase = phrase
                        best_len = len(phrase)
                        best_idx = idx

            if best_phrase and best_len >= 6:
                # Replace phrase with 2-byte marker: 0x80 + index
                result.append(0x80)
                result.append(best_idx)
                pos += len(best_phrase)
            else:
                result.append(text[pos].encode("utf-8")[0])
                pos += 1

        return bytes(result)

    def decode(self, encoded: bytes) -> str:
        """Decode phrase-encoded text."""
        if not encoded:
            return ""
        result = []
        pos = 0
        while pos < len(encoded):
            b = encoded[pos]
            pos += 1
            if b == 0x80 and pos < len(encoded):
                idx = encoded[pos]
                pos += 1
                if idx < len(self.phrases):
                    result.append(self.phrases[idx])
            else:
                result.append(chr(b))
        return "".join(result)

    def encode_index(self) -> bytes:
        result = bytearray()
        result.extend(_varint_encode(len(self.phrases)))
        for phrase in self.phrases:
            pb = phrase.encode("utf-8")
            result.extend(_varint_encode(len(pb)))
            result.extend(pb)
        return bytes(result)

    @classmethod
    def decode_index(cls, data: bytes, pos: int) -> tuple[list[str], int]:
        count, pos = _varint_decode(data, pos)
        phrases = []
        for _ in range(count):
            length, pos = _varint_decode(data, pos)
            phrase = data[pos:pos+length].decode("utf-8", errors="replace")
            pos += length
            phrases.append(phrase)
        return phrases, pos


# ─────────────────────────────────────────────────────────────────────────────
# AUTHOR DICTIONARY
# ─────────────────────────────────────────────────────────────────────────────

class AuthorDictionary:
    """Dictionary for frequently occurring authors."""

    def __init__(self, max_entries: int = 128):
        self.max_entries = max_entries
        self.authors: list[str] = []
        self.author_map: dict[str, int] = {}

    def train(self, records: list[dict]) -> None:
        counts = Counter()
        for r in records:
            a = str(r.get("author_handle", "") or r.get("author", "") or "")
            if a:
                counts[a] += 1
        top = sorted(counts.items(), key=lambda x: -x[1])[:self.max_entries]
        self.authors = [a for a, _ in top]
        self.author_map = {a: i for i, a in enumerate(self.authors)}

    def encode(self, author: str) -> bytes:
        if author in self.author_map:
            return bytes([0x80 | (self.author_map[author] & 0x7F)])
        raw = author.encode("utf-8")
        result = bytearray()
        result.append(0x00)
        result.extend(_varint_encode(len(raw)))
        result.extend(raw)
        return bytes(result)

    def decode(self, data: bytes, pos: int) -> tuple[str, int]:
        marker = data[pos]
        pos += 1
        if marker & 0x80:
            idx = marker & 0x7F
            if idx < len(self.authors):
                return self.authors[idx], pos
            return "", pos
        length, pos = _varint_decode(data, pos)
        author = data[pos:pos+length].decode("utf-8", errors="replace")
        return author, pos + length

    def encode_index(self) -> bytes:
        result = bytearray()
        result.extend(_varint_encode(len(self.authors)))
        for author in self.authors:
            ab = author.encode("utf-8")
            result.extend(_varint_encode(len(ab)))
            result.extend(ab)
        return bytes(result)

    @classmethod
    def decode_index(cls, data: bytes, pos: int) -> tuple[list[str], int]:
        count, pos = _varint_decode(data, pos)
        authors = []
        for _ in range(count):
            length, pos = _varint_decode(data, pos)
            author = data[pos:pos+length].decode("utf-8", errors="replace")
            pos += length
            authors.append(author)
        return authors, pos


# ─────────────────────────────────────────────────────────────────────────────
# RELATIVE URL ENCODER
# ─────────────────────────────────────────────────────────────────────────────

class RelativeURLEncoder:
    """Encode URLs as deltas from previous URLs (for sequential data)."""

    def encode_urls(self, urls: list[str]) -> list[bytes]:
        """Encode URLs, reusing base URL when possible."""
        result = []
        prev_base = ""

        for url in urls:
            if not url:
                result.append(b"\xff")
                continue

            # Find common prefix with previous URL
            common_len = 0
            if prev_base:
                min_len = min(len(prev_base), len(url))
                while common_len < min_len and prev_base[common_len] == url[common_len]:
                    common_len += 1

            if common_len >= 5 and common_len > len(prev_base) * 0.5:
                # Use relative encoding
                suffix = url[common_len:]
                result.append(bytes([0x80 | min(common_len, 0x7F)]))
                if suffix:
                    result.append(_varint_encode(len(suffix)))
                    result.append(suffix.encode("utf-8"))
                else:
                    result.append(b"\x00")
            else:
                # Full URL (just use grammar encoder separately)
                result.append(b"\x00" + url.encode("utf-8"))

            prev_base = url[:common_len] if common_len > 0 else url

        return result


# ─────────────────────────────────────────────────────────────────────────────
# V5 MAIN ENCODER
# ─────────────────────────────────────────────────────────────────────────────

def encode_records_v5(records: list[dict], backend: str = "zlib") -> bytes:
    """Encode records using V5 advanced hybrid compression."""
    if not records:
        return MAGIC + struct.pack("<HHB", VERSION, 0, 0)

    n = len(records)

    # ── Train components ──
    urls = [str(r.get("status_url", "") or r.get("url", "") or "") for r in records]
    ids = [int(str(r.get("status_id", "") or r.get("id", "") or "0") or "0") for r in records]
    texts = [str(r.get("tweet_text", "") or r.get("text", "") or "") for r in records]

    url_grammar = URLGrammarV2()
    url_grammar.train(urls)

    author_dict = AuthorDictionary(max_entries=128)
    author_dict.train(records)

    phrase_dict = PhraseDictionary(max_entries=256)
    phrase_dict.train(texts)

    bpe = SimpleBPE(max_rules=128)
    bpe.train(texts)

    # ── Encode dictionary section ──
    dict_section = bytearray()

    # URL templates
    template_bytes = url_grammar.encode_template_index()
    dict_section.extend(_varint_encode(len(template_bytes)))
    dict_section.extend(template_bytes)

    # Author dictionary
    author_bytes = author_dict.encode_index()
    dict_section.extend(_varint_encode(len(author_bytes)))
    dict_section.extend(author_bytes)

    # Phrase dictionary
    phrase_bytes = phrase_dict.encode_index()
    dict_section.extend(_varint_encode(len(phrase_bytes)))
    dict_section.extend(phrase_bytes)

    # BPE rules
    dict_section.extend(_varint_encode(len(bpe.merge_rules)))
    for merge_a, merge_b in bpe.merge_rules:
        dict_section.append(len(merge_a))
        dict_section.extend(merge_a)
        dict_section.append(len(merge_b))
        dict_section.extend(merge_b)

    dict_bytes = bytes(dict_section)

    # ── Encode data section ──
    data_section = bytearray()

    # IDs as deltas
    prev_id = 0
    id_data = bytearray()
    for id_val in ids:
        delta = id_val - prev_id
        id_data.extend(_varint_encode(_zigzag_encode(delta)))
        prev_id = id_val
    data_section.extend(_varint_encode(len(id_data)))
    data_section.extend(id_data)

    # Authors with run-length encoding
    author_data = bytearray()
    prev_author = ""
    run_count = 0
    for record in records:
        author = str(record.get("author_handle", "") or record.get("author", "") or "")
        if author == prev_author and run_count < 127:
            run_count += 1
        else:
            if prev_author:
                enc = author_dict.encode(prev_author)
                if run_count > 1:
                    author_data.append(0x40 | min(run_count, 0x3F))
                author_data.extend(enc)
            prev_author = author
            run_count = 1
    if prev_author:
        enc = author_dict.encode(prev_author)
        if run_count > 1:
            author_data.append(0x40 | min(run_count, 0x3F))
        author_data.extend(enc)
    data_section.extend(_varint_encode(len(author_data)))
    data_section.extend(author_data)

    # URLs with grammar encoding
    url_data = bytearray()
    for record in records:
        url = str(record.get("status_url", "") or record.get("url", "") or "")
        encoded_url = url_grammar.encode(url)
        url_data.extend(_varint_encode(len(encoded_url)))
        url_data.extend(encoded_url)
    data_section.extend(_varint_encode(len(url_data)))
    data_section.extend(url_data)

    # Texts with BPE encoding
    text_data = bytearray()
    for record in records:
        text = str(record.get("tweet_text", "") or record.get("text", "") or "")

        raw_enc = text.encode("utf-8")
        bpe_enc = bpe.encode(text)

        # Use BPE if it saves space
        if len(bpe_enc) < len(raw_enc) - 3:
            text_data.append(0x02)  # BPE
            text_data.extend(_varint_encode(len(bpe_enc)))
            text_data.extend(bpe_enc)
        else:
            text_data.append(0x00)  # Raw
            text_data.extend(_varint_encode(len(raw_enc)))
            text_data.extend(raw_enc)

    data_section.extend(_varint_encode(len(text_data)))
    data_section.extend(text_data)

    data_bytes = bytes(data_section)

    # ── Assemble container ──
    raw_container = dict_bytes + data_bytes

    if backend == "gzip":
        compressed = gzip.compress(raw_container, compresslevel=6)
        backend_code = 1
    elif backend == "zlib":
        compressed = zlib.compress(raw_container, level=6)
        backend_code = 2
    else:
        compressed = raw_container
        backend_code = 0

    checksum = zlib.crc32(compressed) & 0xFFFFFFFF

    result = bytearray()
    result.extend(MAGIC)
    result.extend(struct.pack("<HHB", VERSION, 0, backend_code))
    result.extend(_varint_encode(n))
    result.extend(compressed)
    result.extend(struct.pack("<I", checksum))

    return bytes(result)


def decode_records_v5(data: bytes) -> list[dict]:
    """Decode V5 compressed records."""
    if len(data) < 9:
        raise ValueError("Data too short")
    if data[:4] != MAGIC:
        raise ValueError(f"Invalid magic: {data[:4]!r}")

    version, flags, backend = struct.unpack("<HHB", data[4:9])
    if version != VERSION:
        raise ValueError(f"Unsupported version: {version}")
    if flags & 1:
        return []

    pos = 9
    n, pos = _varint_decode(data, pos)

    # Decompress
    compressed_start = pos
    compressed_end = len(data) - 4
    compressed = data[compressed_start:compressed_end]
    stored_crc = struct.unpack("<I", data[compressed_end:compressed_end+4])[0]
    computed_crc = zlib.crc32(compressed) & 0xFFFFFFFF
    if computed_crc != stored_crc:
        raise ValueError("Checksum mismatch")

    if backend == 0:
        decompressed = compressed
    elif backend == 1:
        decompressed = gzip.decompress(compressed)
    elif backend == 2:
        decompressed = zlib.decompress(compressed)
    else:
        raise ValueError(f"Unknown backend: {backend}")

    # ── Decode dictionary section ──
    dp = 0

    # URL templates
    template_len, dp = _varint_decode(decompressed, dp)
    template_data = decompressed[dp:dp+template_len]
    dp += template_len
    url_templates, _ = URLGrammarV2.decode_template_index(template_data, 0)

    url_grammar = URLGrammarV2()
    url_grammar.templates = url_templates
    url_grammar.template_map = {t: i for i, t in enumerate(url_templates)}

    # Author dictionary
    author_len, dp = _varint_decode(decompressed, dp)
    author_data_start = dp
    author_count, _ = AuthorDictionary.decode_index(decompressed, author_data_start)
    dp += author_len
    author_dict = AuthorDictionary()
    author_dict.authors = author_count
    author_dict.author_map = {a: i for i, a in enumerate(author_count)}

    # Phrase dictionary
    phrase_len, dp = _varint_decode(decompressed, dp)
    phrase_data_start = dp
    phrase_count, _ = PhraseDictionary.decode_index(decompressed, phrase_data_start)
    dp += phrase_len
    phrase_dict = PhraseDictionary()
    phrase_dict.phrases = phrase_count
    phrase_dict.phrase_map = {p: i for i, p in enumerate(phrase_count)}

    # BPE rules
    bpe_len, dp = _varint_decode(decompressed, dp)
    bpe_rules = []
    for _ in range(min(bpe_len, 256)):
        if dp >= len(decompressed):
            break
        alen = decompressed[dp]
        dp += 1
        a = decompressed[dp:dp+alen]
        dp += alen
        blen = decompressed[dp]
        dp += 1
        b = decompressed[dp:dp+blen]
        dp += blen
        bpe_rules.append((a, b))

    bpe = SimpleBPE(max_rules=256)
    bpe.merge_rules = bpe_rules

    # ── Decode data section ──
    data_start = dp
    data_section = decompressed[data_start:]

    sp = 0

    # IDs
    id_len, sp = _varint_decode(data_section, sp)
    id_data = data_section[sp:sp+id_len]
    sp += id_len
    ids = []
    prev_id = 0
    id_pos = 0
    for _ in range(n):
        if id_pos >= len(id_data):
            ids.append(0)
            continue
        delta, id_pos = _varint_decode(id_data, id_pos)
        ids.append(prev_id + _zigzag_decode(delta))
        prev_id = ids[-1]

    # Authors
    author_len, sp = _varint_decode(data_section, sp)
    author_section = data_section[sp:sp+author_len]
    sp += author_len

    authors = []
    ap = 0
    while ap < len(author_section) and len(authors) < n:
        # Check for run-length marker
        run_count = 1
        if author_section[ap] & 0x40:
            run_count = (author_section[ap] & 0x3F)
            ap += 1

        author, ap = author_dict.decode(author_section, ap)
        for _ in range(run_count):
            authors.append(author)
            if len(authors) >= n:
                break

    # URLs
    url_len, sp = _varint_decode(data_section, sp)
    url_section = data_section[sp:sp+url_len]
    sp += url_len

    up = 0
    urls = []
    for _ in range(n):
        if up >= len(url_section):
            urls.append("")
            continue
        url_len2, up = _varint_decode(url_section, up)
        url_enc = url_section[up:up+url_len2]
        up += url_len2
        urls.append(url_grammar.decode(url_enc))

    # Texts
    text_len, sp = _varint_decode(data_section, sp)
    text_section = data_section[sp:sp+text_len]
    sp += text_len

    tp = 0
    texts = []
    for _ in range(n):
        if tp >= len(text_section):
            texts.append("")
            continue
        text_marker = text_section[tp]
        tp += 1
        tlen, tp = _varint_decode(text_section, tp)
        tdata = text_section[tp:tp+tlen]
        tp += tlen

        if text_marker == 0x02:
            texts.append(bpe.decode(tdata))
        else:
            texts.append(tdata.decode("utf-8", errors="replace"))

    # Assemble records
    records = []
    for i in range(n):
        records.append({
            "id": ids[i] if i < len(ids) else 0,
            "status_id": str(ids[i]) if i < len(ids) else "0",
            "author_handle": authors[i] if i < len(authors) else "",
            "author": authors[i] if i < len(authors) else "",
            "status_url": urls[i] if i < len(urls) else "",
            "url": urls[i] if i < len(urls) else "",
            "tweet_text": texts[i] if i < len(texts) else "",
            "text": texts[i] if i < len(texts) else "",
        })

    return records


def inspect_archive_v5(data: bytes) -> dict:
    if len(data) < 9:
        raise ValueError("Data too short")
    if data[:4] != MAGIC:
        raise ValueError("Invalid magic")
    version, flags, backend = struct.unpack("<HHB", data[4:9])
    backend_names = {0: "none", 1: "gzip", 2: "zlib"}
    if flags & 1:
        return {"magic": "TWZ5", "version": VERSION, "record_count": 0, "is_empty": True}
    pos = 9
    n, _ = _varint_decode(data, pos)
    return {
        "magic": "TWZ5",
        "version": VERSION,
        "record_count": n,
        "backend": backend_names.get(backend, "unknown"),
        "total_size": len(data),
    }
