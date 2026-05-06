#!/usr/bin/env python3
"""
TweetZip Compression Benchmark: V1 vs V2 vs Real-World

Tests on multiple synthetic corpus types that mimic real-world data.
NO external downloads - all data is generated programmatically.
"""

import gzip
import json
import random
import statistics
import string
import sys
import time
import zlib
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from tweetkb.compress import decode_records as decode_v1
from tweetkb.compress import encode_records as encode_v1
from tweetkb.compress_v2 import decode_records_v2, encode_records_v2
from tweetkb.compress_v3 import decode_records_v3, encode_records_v3
from tweetkb.compress_v4 import decode_records_v4, encode_records_v4
from tweetkb.compress_v5 import decode_records_v5, encode_records_v5
from tweetkb.compress_v6 import decode_records_v6, encode_records_v6

# ═══════════════════════════════════════════════════════════════════════════
# SYNTHETIC DATA GENERATORS - NO EXTERNAL DOWNLOADS
# ═══════════════════════════════════════════════════════════════════════════

class SyntheticCorpus:
    """Generate synthetic data that mimics real-world patterns."""

    # Common domains, authors, phrases for bookmark-like data
    DOMAINS = [
        "x.com", "twitter.com", "github.com", "arxiv.org", "huggingface.co",
        "stackoverflow.com", "reddit.com", "news.ycombinator.com",
        "youtube.com", "medium.com", "dev.to", "blog.google",
        "anthropic.com", "openai.com", "deepmind.google",
    ]

    HANDLES = [f"@user{i}" for i in range(50)] + [
        "@sama", "@dabooth", "@ylecun", "@kaboro", "@ylecun",
        "@AbacusAI", "@emollick", "@bindureddy", "@j友好的",
    ]

    AI_TOPICS = [
        "transformer", "attention mechanism", "RLHF", "chain-of-thought",
        "Constitutional AI", "scaling laws", "emergent capabilities",
        "mechanistic interpretability", "representation engineering",
        "mixture of experts", "sparse attention", "test-time compute",
        "inference scaling", "MoE", "RAG", "fine-tuning", "alignment",
        "safety", "capabilities", "reasoning", "multimodal", "LLM",
    ]

    TOOLS = [
        "Cursor", "Copilot", "Claude Code", "Windsurf", "Codeium",
        "Tabnine", "Amazon CodeWhisperer", "Replit Agent", "bolt.new",
        "v0", "Lovable", "Midjourney", "DALL-E 3", "Sora",
        "Stable Diffusion", "Runway", "ElevenLabs", "Vercel",
    ]

    FRAMEWORKS = [
        "PyTorch", "TensorFlow", "JAX", "FastAPI", "Next.js", "React",
        "SvelteKit", "Astro", "Nuxt", "Django", "Flask", "Hono",
        "Express", "LangChain", "LlamaIndex", "CrewAI", "AutoGen",
        "Turso", "Neon", "Supabase", "D1", "Prisma", "Drizzle",
    ]

    PHRASES = [
        "This is really interesting and worth exploring further.",
        "The results are impressive but we need more benchmarks.",
        "Has anyone tried this with smaller models?",
        "The paper is available on arxiv with more details.",
        "I built a version of this last year - happy to share code.",
        "The key insight is that scaling alone doesn't solve everything.",
        "Hot take: most AI products are just wrappers around GPT-4.",
        "Unpopular opinion: transformers are overrated for reasoning.",
        "The future is multimodal and embedded in every product.",
        "This changes everything we know about alignment.",
        "Open source wins in the long run - history proves it.",
        "Closed models will dominate until regulation catches up.",
        "The real bottleneck is data quality, not model size.",
        "Inference cost is the new GPU cost - optimize for it.",
        "Context length is being commoditized - next is agents.",
    ]

    STATUS_PREFIXES = [
        "Just used", "Building with", "Exploring", "Testing",
        "Comparing", "Hot take:", "Unpopular opinion:", "This changes",
        "The future of", "Why", "How", "What if", "Has anyone tried",
        "I built", "Check out", "Amazing thread:", "Key insight:",
        "Thread:", "Summary:", "PSA:", "FYI:", "TIL that",
    ]

    @staticmethod
    def generate_bookmarks(n: int, repeat_factor: float = 0.3) -> list[dict]:
        """Generate bookmark-like records with realistic repetition patterns."""
        records = []
        for i in range(n):
            status_id = 1700000000000 + i

            # Author with repetition
            if i > 0 and random.random() < repeat_factor:
                author = records[-1].get("author_handle", "") or random.choice(SyntheticCorpus.HANDLES)
            else:
                author = random.choice(SyntheticCorpus.HANDLES)

            # URL with repetition
            if i > 0 and random.random() < repeat_factor * 1.5:
                domain = random.choice(SyntheticCorpus.DOMAINS)
                if domain in ["x.com", "twitter.com"]:
                    path = f"/{author[1:]}/status/{status_id}"
                elif domain == "github.com":
                    path = f"/{author[1:]}/project/{i % 20}"
                elif domain == "arxiv.org":
                    path = f"/abs/{17000000 + i % 1000}"
                else:
                    path = f"/post/{i % 100}"
                url = f"https://{domain}{path}"
            else:
                domain = random.choice(SyntheticCorpus.DOMAINS)
                if domain == "arxiv.org":
                    url = f"https://{domain}/abs/{17000000 + i}"
                else:
                    url = f"https://{domain}/post/{i}"

            # Text with repeated phrases and templates
            if random.random() < 0.25:
                # Highly compressible template
                templates = [
                    lambda: f"{random.choice(SyntheticCorpus.STATUS_PREFIXES)} {random.choice(SyntheticCorpus.TOOLS)} with {random.choice(SyntheticCorpus.AI_TOPICS)} - {random.choice(SyntheticCorpus.PHRASES)}",
                    lambda: f"Interesting paper on {random.choice(SyntheticCorpus.AI_TOPICS)}: {random.choice(SyntheticCorpus.AI_TOPICS)} + {random.choice(SyntheticCorpus.FRAMEWORKS)} = win",
                    lambda: f"Building with {random.choice(SyntheticCorpus.FRAMEWORKS)} + {random.choice(SyntheticCorpus.TOOLS)}. {random.choice(SyntheticCorpus.AI_TOPICS)} is the future.",
                    lambda: f"Hot take: {random.choice(SyntheticCorpus.AI_TOPICS)} at {random.choice(SyntheticCorpus.DOMAINS)} is overrated. {random.choice(SyntheticCorpus.PHRASES)}",
                    lambda: f"New research: {random.choice(SyntheticCorpus.AI_TOPICS)} outperforms {random.choice(SyntheticCorpus.AI_TOPICS)} on {random.choice(SyntheticCorpus.AI_TOPICS)} benchmarks.",
                ]
                text = random.choice(templates)()
            elif random.random() < 0.5:
                # Semi-unique
                text = f"{random.choice(SyntheticCorpus.STATUS_PREFIXES)} {random.choice(SyntheticCorpus.AI_TOPICS)} and {random.choice(SyntheticCorpus.TOOLS)}. {random.choice(SyntheticCorpus.PHRASES)}"
            else:
                # Unique-ish
                words = random.sample(SyntheticCorpus.AI_TOPICS + SyntheticCorpus.TOOLS + SyntheticCorpus.FRAMEWORKS, k=random.randint(8, 20))
                text = " ".join(words) + f". See more at {url}"

            records.append({
                "id": status_id,
                "status_id": str(status_id),
                "author_handle": author,
                "author": author,
                "status_url": url,
                "url": url,
                "tweet_text": text,
                "text": text,
            })

        return records

    @staticmethod
    def generate_text_corpus(n_bytes: int, vocab_size: int = 1000) -> bytes:
        """Generate realistic-looking English text."""
        # Build a word list
        words = []
        for _ in range(vocab_size):
            length = random.randint(3, 12)
            word = ''.join(random.choices(string.ascii_lowercase, k=length))
            words.append(word)

        # Add some common words with higher frequency
        common_words = ["the", "a", "an", "is", "are", "was", "were", "be", "been",
                       "have", "has", "had", "do", "does", "did", "will", "would",
                       "could", "should", "may", "might", "must", "shall", "can",
                       "this", "that", "these", "those", "it", "its", "they",
                       "them", "their", "we", "us", "our", "you", "your", "I", "my",
                       "and", "or", "but", "if", "then", "else", "when", "where",
                       "how", "what", "why", "which", "who", "whom", "whose",
                       "not", "no", "yes", "all", "some", "any", "each", "every",
                       "both", "few", "more", "most", "other", "such", "only",
                       "own", "same", "so", "than", "too", "very", "just", "also"]
        words = common_words * 5 + words

        # Generate text with word-level patterns
        result = []
        current_len = 0
        sentences = [
            "The system works as expected and produces good results.",
            "This is a common pattern in machine learning applications.",
            "Users should be aware of the implications and trade-offs.",
            "The data shows significant improvements over baseline methods.",
            "Further research is needed to understand the underlying mechanisms.",
            "The approach is based on established principles and proven techniques.",
            "Results indicate that the method is both efficient and reliable.",
            "Analysis reveals several key factors that contribute to success.",
            "Implementation requires careful attention to detail and testing.",
            "The findings suggest that this approach has broad applicability.",
        ]
        sentences.extend(common_words)

        while current_len < n_bytes:
            if random.random() < 0.1:
                text = random.choice(sentences)
            else:
                num_words = random.randint(5, 15)
                text_words = random.choices(words, k=num_words)
                text_words[0] = text_words[0].capitalize()
                text = ' '.join(text_words) + '.'

            result.append(text)
            result.append(' ')
            current_len += len(text) + 1

        return ''.join(result)[:n_bytes].encode('utf-8')

    @staticmethod
    def generate_code_corpus(n_bytes: int) -> bytes:
        """Generate Python-like code."""
        types_ = ["int", "str", "bool", "float", "list", "dict", "set", "tuple",
                 "Optional", "List", "Dict", "Any", "Union", "Callable", "bytes"]

        names = ["data", "result", "value", "item", "index", "key", "count",
                "total", "output", "input", "config", "options", "params",
                "handler", "manager", "processor", "service", "client"]

        patterns = [
            "def {name}({name2}: {type_}) -> {type_}:\n    return {name2}",
            "for {name} in {name2}s:\n    if {name} is not None:\n        {name2} = {name}",
            "with open('{name}.txt', 'r') as f:\n    data = f.read()",
            "class {Name}(BaseModel):\n    {name}: {type_}\n    {name2}: {type_}",
            "result = {name}({name2}={name3}) if {name4} else default",
            "@app.get('/{name}')\nasync def get_{name}():\n    return {{'data': []}}",
            "{name}s = [{name}({type_}=i) for i in range(100)]",
            "try:\n    {name} = await {name2}.process()\nexcept Exception as e:\n    {name3} = str(e)",
            "if __name__ == '__main__':\n    main()",
        ]

        result = []
        current_len = 0

        while current_len < n_bytes:
            pattern = random.choice(patterns)
            code = pattern.format(
                name=random.choice(names),
                name2=random.choice(names),
                name3=random.choice(names),
                name4=random.choice(names),
                Name=random.choice(names).capitalize(),
                type_=random.choice(types_),
            )
            result.append(code)
            result.append('\n\n')
            current_len += len(code) + 2

        return ''.join(result)[:n_bytes].encode('utf-8')


# ═══════════════════════════════════════════════════════════════════════════
# BENCHMARK FRAMEWORK
# ═══════════════════════════════════════════════════════════════════════════

def benchmark_encode_decode(
    name: str,
    encode_fn: Callable,
    decode_fn: Callable,
    data: bytes,
    iterations: int = 3,
    is_binary: bool = False,
) -> dict:
    """Benchmark a compression method on raw bytes."""
    if is_binary:
        original_size = len(data)
    else:
        original_size = len(data)

    # Warm-up
    encoded = encode_fn(data)

    # Encode timing
    encode_times = []
    for _ in range(iterations):
        start = time.perf_counter()
        encoded = encode_fn(data)
        encode_times.append(time.perf_counter() - start)

    compressed_size = len(encoded)

    # Decode timing
    decode_times = []
    decoded_data = None
    for _ in range(iterations):
        start = time.perf_counter()
        decoded_data = decode_fn(encoded)
        decode_times.append(time.perf_counter() - start)

    # Verify roundtrip
    if is_binary:
        roundtrip_ok = len(decoded_data) == len(data)
    else:
        roundtrip_ok = decoded_data == data

    return {
        "name": name,
        "original_bytes": original_size,
        "compressed_bytes": compressed_size,
        "ratio": original_size / compressed_size if compressed_size > 0 else 0,
        "encode_mean_ms": statistics.mean(encode_times) * 1000,
        "encode_std_ms": (statistics.stdev(encode_times) * 1000 if len(encode_times) > 1 else 0),
        "decode_mean_ms": statistics.mean(decode_times) * 1000,
        "decode_std_ms": (statistics.stdev(decode_times) * 1000 if len(decode_times) > 1 else 0),
        "throughput_mbps": (original_size / statistics.mean(encode_times) / 1e6) if encode_times else 0,
        "roundtrip_ok": roundtrip_ok,
    }


def benchmark_records(
    name: str,
    encode_fn: Callable,
    decode_fn: Callable,
    records: list[dict],
    iterations: int = 3,
) -> dict:
    """Benchmark on record list (JSON baseline comparison)."""
    # JSON baseline
    json_bytes = b"".join(json.dumps(r).encode("utf-8") + b"\n" for r in records)
    json_size = len(json_bytes)

    # Gzip baseline
    gzip_bytes = gzip.compress(json_bytes)

    # Warm-up
    encoded = encode_fn(records)

    # Encode timing
    encode_times = []
    for _ in range(iterations):
        start = time.perf_counter()
        encoded = encode_fn(records)
        encode_times.append(time.perf_counter() - start)

    compressed_size = len(encoded)

    # Decode timing
    decode_times = []
    decoded_records = None
    for _ in range(iterations):
        start = time.perf_counter()
        decoded_records = decode_fn(encoded)
        decode_times.append(time.perf_counter() - start)

    roundtrip_ok = len(decoded_records) == len(records) if decoded_records else False

    return {
        "name": name,
        "json_size": json_size,
        "gzip_size": len(gzip_bytes),
        "compressed_bytes": compressed_size,
        "json_ratio": json_size / compressed_size if compressed_size > 0 else 0,
        "gzip_ratio": len(gzip_bytes) / compressed_size if compressed_size > 0 else 0,
        "encode_mean_ms": statistics.mean(encode_times) * 1000,
        "decode_mean_ms": statistics.mean(decode_times) * 1000,
        "records_per_sec": len(records) / statistics.mean(decode_times) if decode_times else 0,
        "roundtrip_ok": roundtrip_ok,
    }


def print_results(results: list[dict], corpus_name: str):
    """Print benchmark results."""
    print(f"\n{'═' * 90}")
    print(f"📊 {corpus_name}")
    print(f"{'═' * 90}")

    results = sorted(results, key=lambda r: -r.get("json_ratio", r.get("ratio", 0)))

    for r in results:
        status = "✓" if r.get("roundtrip_ok") else "✗"
        ratio = r.get("json_ratio", r.get("ratio", 0))
        compressed = r.get("compressed_bytes", 0)
        original = r.get("json_size", r.get("original_bytes", 0))

        if "encode_mean_ms" in r:
            print(f"\n  {r['name']} [{status}]")
            print(f"    Size:        {original:,} → {compressed:,} bytes ({ratio:.2f}x vs JSON)")
            print(f"    vs gzip:     {r.get('gzip_ratio', 0):.2f}x")
            print(f"    Encode:      {r['encode_mean_ms']:.1f} ± {r.get('encode_std_ms', 0):.1f} ms")
            print(f"    Decode:      {r['decode_mean_ms']:.1f} ± {r.get('decode_std_ms', 0):.1f} ms")
            print(f"    Throughput:  {r.get('records_per_sec', 0):,.0f} records/sec")
        else:
            print(f"\n  {r['name']} [{status}]")
            print(f"    Size:        {original:,} → {compressed:,} bytes ({ratio:.2f}x)")
            print(f"    Encode:      {r['encode_mean_ms']:.1f} ms")
            print(f"    Decode:      {r['decode_mean_ms']:.1f} ms")
            print(f"    Throughput:  {r['throughput_mbps']:.1f} MB/s")


def main():
    print("=" * 90)
    print("TWEETZIP COMPRESSION BENCHMARK - Synthetic Data, No External Downloads")
    print("=" * 90)

    all_results = {}

    # ── Test 1: Bookmark records (structured JSON-like) ──────────────────
    print("\nGenerating bookmark corpus...")
    for size_label, n_records in [("100", 100), ("1K", 1000), ("10K", 10000)]:
        print(f"  Generating {n_records} bookmarks...", end=" ", flush=True)
        records = SyntheticCorpus.generate_bookmarks(n_records, repeat_factor=0.3)
        print("done")

        corpus_name = f"Bookmarks ({size_label})"
        results = []

        # JSONL baseline
        json_bytes = b"".join(json.dumps(r).encode("utf-8") + b"\n" for r in records)
        gzip_bytes = gzip.compress(json_bytes)
        results.append({
            "name": "JSONL Baseline",
            "json_size": len(json_bytes),
            "gzip_size": len(gzip_bytes),
            "compressed_bytes": len(json_bytes),
            "json_ratio": 1.0,
            "gzip_ratio": len(json_bytes) / len(gzip_bytes),
            "encode_mean_ms": 0,
            "decode_mean_ms": 0,
            "roundtrip_ok": True,
        })
        results.append({
            "name": "gzip(JSONL)",
            "json_size": len(json_bytes),
            "gzip_size": len(gzip_bytes),
            "compressed_bytes": len(gzip_bytes),
            "json_ratio": len(json_bytes) / len(gzip_bytes),
            "gzip_ratio": 1.0,
            "encode_mean_ms": 0,
            "decode_mean_ms": 0,
            "roundtrip_ok": True,
        })

        # V1
        print(f"  Benchmarking V1 on {size_label}...", end=" ", flush=True)
        try:
            results.append(benchmark_records("V1: Dictionary", encode_v1, decode_v1, records, iterations=3))
            print("done")
        except Exception as e:
            print(f"FAILED: {e}")

        # V2
        print(f"  Benchmarking V2 on {size_label}...", end=" ", flush=True)
        try:
            results.append(benchmark_records("V2: ADGLP", encode_records_v2, decode_records_v2, records, iterations=3))
            print("done")
        except Exception as e:
            print(f"FAILED: {e}")

        # V3
        print(f"  Benchmarking V3 on {size_label}...", end=" ", flush=True)
        try:
            results.append(benchmark_records("V3: SDRGC", encode_records_v3, decode_records_v3, records, iterations=3))
            print("done")
        except Exception as e:
            print(f"FAILED: {e}")

        # V4 (raw)
        print(f"  Benchmarking V4-raw on {size_label}...", end=" ", flush=True)
        try:
            results.append(benchmark_records("V4: Hybrid (raw)", encode_records_v4, decode_records_v4, records, iterations=3))
            print("done")
        except Exception as e:
            print(f"FAILED: {e}")

        # V4 (gzip)
        print(f"  Benchmarking V4-gzip on {size_label}...", end=" ", flush=True)
        try:
            enc_fn = lambda r: encode_records_v4(r, backend='gzip')
            results.append(benchmark_records("V4: Hybrid + gzip", enc_fn, decode_records_v4, records, iterations=3))
            print("done")
        except Exception as e:
            print(f"FAILED: {e}")

        # V4 (zlib)
        print(f"  Benchmarking V4-zlib on {size_label}...", end=" ", flush=True)
        try:
            enc_fn = lambda r: encode_records_v4(r, backend='zlib')
            results.append(benchmark_records("V4: Hybrid + zlib", enc_fn, decode_records_v4, records, iterations=3))
            print("done")
        except Exception as e:
            print(f"FAILED: {e}")

        # V5 (with BPE)
        print(f"  Benchmarking V5 on {size_label}...", end=" ", flush=True)
        try:
            enc_fn = lambda r: encode_records_v5(r, backend='zlib')
            results.append(benchmark_records("V5: Hybrid + BPE + zlib", enc_fn, decode_records_v5, records, iterations=3))
            print("done")
        except Exception as e:
            print(f"FAILED: {e}")

        # V6 (reference encoding + zlib level 9)
        print(f"  Benchmarking V6 on {size_label}...", end=" ", flush=True)
        try:
            enc_fn = lambda r: encode_records_v6(r, backend='zlib')
            results.append(benchmark_records("V6: Ref + zlib-9", enc_fn, decode_records_v6, records, iterations=3))
            print("done")
        except Exception as e:
            print(f"FAILED: {e}")

        all_results[corpus_name] = results
        print_results(results, corpus_name)

    # ── Test 2: Raw text corpus ───────────────────────────────────────────
    print("\nGenerating text corpus...")
    for size_label, n_bytes in [("1MB", 1_000_000), ("10MB", 10_000_000)]:
        print(f"  Generating {n_bytes:,} bytes...", end=" ", flush=True)
        text_data = SyntheticCorpus.generate_text_corpus(n_bytes)
        print(f"done ({len(text_data):,} bytes)")

        corpus_name = f"Text ({size_label})"
        results = []

        # Baseline
        results.append({
            "name": "Raw Text",
            "original_bytes": len(text_data),
            "compressed_bytes": len(text_data),
            "ratio": 1.0,
            "encode_mean_ms": 0,
            "decode_mean_ms": 0,
            "throughput_mbps": 0,
            "roundtrip_ok": True,
        })

        # Gzip
        gzip_data = gzip.compress(text_data)
        results.append({
            "name": "gzip",
            "original_bytes": len(text_data),
            "compressed_bytes": len(gzip_data),
            "ratio": len(text_data) / len(gzip_data),
            "encode_mean_ms": 0,
            "decode_mean_ms": 0,
            "throughput_mbps": 0,
            "roundtrip_ok": True,
        })

        # zlib (level 9)
        zlib_data = zlib.compress(text_data, level=9)
        results.append({
            "name": "zlib-9",
            "original_bytes": len(text_data),
            "compressed_bytes": len(zlib_data),
            "ratio": len(text_data) / len(zlib_data),
            "encode_mean_ms": 0,
            "decode_mean_ms": 0,
            "throughput_mbps": 0,
            "roundtrip_ok": True,
        })

        # Zstandard (if available)
        try:
            import zstandard as zstd
            cctx = zstd.ZstdCompressor(level=3)
            zstd_data = cctx.compress(text_data)
            results.append({
                "name": "Zstandard-3",
                "original_bytes": len(text_data),
                "compressed_bytes": len(zstd_data),
                "ratio": len(text_data) / len(zstd_data),
                "encode_mean_ms": 0,
                "decode_mean_ms": 0,
                "throughput_mbps": 0,
                "roundtrip_ok": True,
            })
        except ImportError:
            pass

        all_results[corpus_name] = results
        print_results(results, corpus_name)

    # ── Summary ──────────────────────────────────────────────────────────
    print("\n" + "=" * 90)
    print("SUMMARY - Best Compression Ratio by Corpus")
    print("=" * 90)

    for corpus_name, results in all_results.items():
        if not results:
            continue
        best = max(results, key=lambda r: r.get("json_ratio", r.get("ratio", 0)))
        best_ratio = best.get("json_ratio", best.get("ratio", 0))
        print(f"\n  {corpus_name}:")
        print(f"    Best: {best['name']} at {best_ratio:.2f}x")

    print("\n" + "=" * 90)
    print("Benchmark complete!")
    print("=" * 90)


if __name__ == "__main__":
    main()
