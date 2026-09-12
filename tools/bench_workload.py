from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from tweetkb.analyzer import run_analysis
from tweetkb.db import Store
from tweetkb.search import search_bookmarks

TEXTS = (
    "New browser agent automation workflow with MCP tool use and playwright",
    "debugging a rust compiler borrow checker error in cargo test",
    "arxiv paper on transformer attention is all you need",
    "obsidian vault local-first knowledge base sqlite sync",
    "gpt-4o claude gemini llama model release quantization",
    "kubernetes docker postgres redis deploy latency throughput",
    "figma ux ui design system tailwind accessibility",
    "swe-bench humaneval mmlu eval leaderboard score",
)


def seed(path: Path, n: int) -> None:
    if path.exists():
        path.unlink()
    store = Store(path, create=True)
    store.init()
    for i in range(n):
        text = TEXTS[i % len(TEXTS)] + f" sample {i}"
        handle = ("alice", "bob", "carol", "karpathy")[i % 4]
        store.upsert_bookmark(
            {
                "status_url": f"https://x.com/{handle}/status/{10_000_000 + i}",
                "author_handle": handle,
                "author_name": handle.title(),
                "tweet_text": text,
                "raw_text": text,
                "links": ["https://github.com/example/repo"] if i % 7 == 0 else [],
            }
        )
    store.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--search", default="")
    parser.add_argument("--analyze", action="store_true")
    args = parser.parse_args()
    if args.seed:
        t0 = time.perf_counter()
        seed(args.db, args.seed)
        print(json.dumps({"seed": args.seed, "seconds": round(time.perf_counter() - t0, 4)}))
        return
    store = Store(args.db, create=False)
    store.init()
    t0 = time.perf_counter()
    if args.search:
        hits = search_bookmarks(store, args.search, limit=50)
        print(json.dumps({"hits": len(hits), "seconds": round(time.perf_counter() - t0, 6)}))
    elif args.analyze:
        result = run_analysis(store, stage="all", provider="local-hash", changed_only=False)
        result["seconds"] = round(time.perf_counter() - t0, 4)
        print(json.dumps(result))
    store.close()


if __name__ == "__main__":
    main()
