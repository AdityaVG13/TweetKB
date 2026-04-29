from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .checkpoint import Checkpoint
from .collector import BrowserHarnessCollector
from .config import load_config
from .db import DEFAULT_DB
from .db import Store as DBStore
from .exporters import ADAPTERS
from .exporters.obsidian import export_obsidian
from .exporters.logseq import export_logseq
from .exporters.markdown import export_markdown
from .exporters.jsonl import export_jsonl
from .exporters.csv import export_csv
from .graph import export_graph_json
from .server import ReviewServer


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tweetkb")
    parser.add_argument("--db", type=Path, default=None)
    parser.add_argument("--browser-app", default=None)
    parser.add_argument("--browser-profile", type=Path, default=None)
    parser.add_argument("--debug-port", type=int, default=None)
    sub = parser.add_subparsers(dest="cmd", required=True)

    # init
    sub.add_parser("init", help="Initialize a fresh database")

    # migrate
    sub.add_parser("migrate", help="Run database migrations")

    # collect
    collect = sub.add_parser("collect")
    collect.add_argument("--limit", type=int, default=100)
    collect.add_argument("--batch-size", type=int, default=20)
    collect.add_argument("--wait", type=float, default=1.5)
    collect.add_argument("--existing-tab", action="store_true")
    collect.add_argument("--normal-chrome", action="store_true")
    collect.add_argument("--apple-events", action="store_true")
    collect.add_argument("--all", action="store_true", help="Collect all bookmarks")

    # enrich
    enrich = sub.add_parser("enrich", help="Open saved X bookmarks and capture full tweet/article content")
    enrich.add_argument("--apple-events", action="store_true", help="Use logged-in Chrome through Apple Events")
    enrich.add_argument("--category", default=None, help="Only enrich a primary category, e.g. business")
    enrich.add_argument("--since", default=None, help="Only enrich bookmarks captured on/after YYYY-MM-DD")
    enrich.add_argument("--limit", type=int, default=25)
    enrich.add_argument("--wait", type=float, default=2.0)
    enrich.add_argument("--all", action="store_true", help="Re-enrich rows that already have captured content")
    enrich.add_argument("--include-links", action="store_true", help="Also open and capture outbound linked pages")
    enrich.add_argument("--max-links", type=int, default=3, help="Max outbound links to read per bookmark")

    # login
    login = sub.add_parser("login")
    login.add_argument("--normal-chrome", action="store_true")

    # chrome-debug
    sub.add_parser("chrome-debug", help="Restart Chrome with remote debugging")

    # analyze
    analyze = sub.add_parser("analyze", help="Run the full analysis pipeline")
    analyze.add_argument("--stage", default="all", choices=["all", "classify", "entities", "embed"])
    analyze.add_argument("--provider", default="local-hash", choices=["local-hash", "ollama", "openai"])
    analyze.add_argument("--changed-only", action="store_true", default=True)
    analyze.add_argument("--no-changed-only", dest="changed_only", action="store_false")

    # classify (legacy, delegates to analyze)
    sub.add_parser("classify", help="Classify bookmarks (alias for analyze --stage classify)")

    # entities
    sub.add_parser("entities", help="Extract entities from all bookmarks")

    # embed
    embed = sub.add_parser("embed", help="Generate embeddings for all bookmarks")
    embed.add_argument("--provider", default="local-hash", choices=["local-hash", "ollama", "openai"])

    # cluster
    cluster = sub.add_parser("cluster", help="Generate topic clusters")
    cluster.add_argument("--min-size", type=int, default=3)
    cluster.add_argument("--min-confidence", type=float, default=0.4)

    # projects
    projects = sub.add_parser("projects", help="Generate project ideas from clusters")
    projects.add_argument("--min-evidence", type=int, default=3)

    # export
    export = sub.add_parser("export", help="Export bookmarks to a knowledge tool")
    export.add_argument("--adapter", "-a", default="obsidian",
                        choices=list(ADAPTERS.keys()))
    export.add_argument("--vault", "--out", "-o", type=Path, required=False)
    export.add_argument("--exclude-category", default="")
    export.add_argument("--include-category", default="")
    export.add_argument("--exclude-review", action="store_true")
    export.add_argument("--min-confidence", type=float, default=0.0)
    export.add_argument("--include-projects", action="store_true", default=True)
    export.add_argument("--include-clusters", action="store_true", default=False)

    # review
    review = sub.add_parser("review", help="Review bookmark actions")
    review_sub = review.add_subparsers(dest="review_cmd", required=True)
    review_list = review_sub.add_parser("list", help="List bookmarks needing review")
    review_list.add_argument("--category", default=None)
    review_list.add_argument("--state", default=None)
    review_list.add_argument("--limit", type=int, default=50)
    review_approve = review_sub.add_parser("approve", help="Approve a bookmark")
    review_approve.add_argument("status_id", help="Tweet status ID")
    review_exclude = review_sub.add_parser("exclude", help="Exclude a bookmark from export")
    review_exclude.add_argument("status_id")
    review_tag = review_sub.add_parser("tag", help="Add a tag to a bookmark")
    review_tag.add_argument("status_id")
    review_tag.add_argument("tag")
    review_junk = review_sub.add_parser("junk", help="List likely junk bookmarks or captures")
    review_junk.add_argument("--limit", type=int, default=50)
    review_open_junk = review_sub.add_parser("open-junk", help="Open likely junk bookmarks in Chrome for manual unbookmarking")
    review_open_junk.add_argument("--limit", type=int, default=10)

    # graph
    graph = sub.add_parser("graph", help="Graph operations")
    graph_sub = graph.add_subparsers(dest="graph_cmd", required=True)
    graph_export = graph_sub.add_parser("export", help="Export knowledge graph")
    graph_export.add_argument("--out", "-o", type=Path, default=Path("exports/graph.json"))

    # compress
    compress = sub.add_parser("compress", help="TweetZip compression")
    compress_sub = compress.add_subparsers(dest="compress_cmd", required=True)
    compress_sub.add_parser("benchmark", help="Benchmark compression")
    compress_export = compress_sub.add_parser("export", help="Export DB to TweetZip")
    compress_export.add_argument("--out", "-o", type=Path, required=True)
    compress_export.add_argument("--engine", default="python", choices=["python", "zig"])
    compress_decompress = compress_sub.add_parser("decompress", help="Decompress TweetZip to JSONL")
    compress_decompress.add_argument("input", type=Path)
    compress_decompress.add_argument("--out", "-o", type=Path, required=True)
    compress_inspect = compress_sub.add_parser("inspect", help="Inspect TweetZip archive")
    compress_inspect.add_argument("input", type=Path)
    compress_verify = compress_sub.add_parser("verify", help="Verify TweetZip archive")
    compress_verify.add_argument("input", type=Path)

    # doctor
    sub.add_parser("doctor", help="Diagnose system health")

    # benchmark
    bench = sub.add_parser("benchmark", help="Run performance benchmarks")
    bench.add_argument("--stage", default="all", choices=["all", "analyze", "export", "compress"])

    # compact
    compact = sub.add_parser("compact", help="Database maintenance")
    compact.add_argument("--vacuum", action="store_true", help="Run VACUUM after stats")
    compact.add_argument("--dry-run", action="store_true", help="Show stats without vacuuming")
    compact.add_argument("--backup", type=Path, default=None, help="Backup path")

    # stats
    sub.add_parser("stats", help="Show database statistics")

    # serve
    serve = sub.add_parser("serve", help="Start the review UI server")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)

    args = parser.parse_args(argv)

    # Resolve db path
    db_path = args.db or load_config().get("database", {}).get("path", str(DEFAULT_DB))
    db_path = Path(db_path)

    try:
        return _dispatch(args, db_path)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if "--debug" in sys.argv:
            raise
        return 1


def _dispatch(args, db_path: Path) -> int:
    store = DBStore(db_path)

    if args.cmd == "init":
        store.init()
        print(f"initialized {db_path}")
        print(f"schema version: {store.schema_version()}")
        return 0

    if args.cmd == "migrate":
        store.init()
        print(f"schema version: {store.schema_version()}")
        return 0

    if args.cmd == "doctor":
        return _cmd_doctor(store, db_path)

    if args.cmd == "stats":
        print(json.dumps(store.stats(), indent=2))
        return 0

    # Commands below need init
    store.init()

    if args.cmd == "chrome-debug":
        collector = _make_collector(store, args)
        collector.start_normal_chrome_debug()
        print("Chrome restarted with remote debugging.")
        return 0

    if args.cmd == "login":
        collector = _make_collector(store, args)
        collector.open_login(normal_chrome=args.normal_chrome)
        return 0

    if args.cmd == "collect":
        collector = _make_collector(store, args)
        collector.ensure_available()
        result = collector.collect(
            args.limit,
            args.batch_size,
            args.wait,
            existing_tab=args.existing_tab,
            normal_chrome=args.normal_chrome,
            apple_events=args.apple_events,
            all_bookmarks=args.all,
        )
        if result.login_required:
            print("X login required. Run `uv run tweetkb login`, finish login, then rerun collect.")
            return 2
        if result.needs_bookmarks_tab:
            if result.debug_targets_empty:
                print("Normal Chrome is open, but Browser-Harness/CDP sees zero tabs. "
                      "Restart normal Chrome with remote debugging enabled:\n"
                      "uv run tweetkb chrome-debug\n"
                      "Then open https://x.com/i/bookmarks and rerun:\n"
                      "uv run tweetkb collect --normal-chrome --existing-tab")
            else:
                suffix = " --normal-chrome" if args.normal_chrome else ""
                print(f"Open https://x.com/i/bookmarks in Chrome, then rerun with `uv run tweetkb collect{suffix} --existing-tab`.")
            return 3
        print(f"saved={result.saved} changed={result.changed} unchanged={result.unchanged} "
              f"seen={result.seen} batches={result.batches}")
        return 0

    if args.cmd == "enrich":
        if not args.apple_events:
            print("Use `uv run tweetkb enrich --apple-events` so the app can read your logged-in Chrome session.")
            return 2
        from .enricher import enrich_with_apple_events

        bookmarks = store.list_bookmarks_for_enrichment(
            category=args.category,
            since=args.since,
            limit=args.limit,
            missing_only=not args.all,
        )
        result = enrich_with_apple_events(
            store,
            bookmarks,
            browser_app=args.browser_app or load_config().get("browser", {}).get("app", "Google Chrome"),
            wait_seconds=args.wait,
            include_links=args.include_links,
            max_links=args.max_links,
        )
        print(f"selected={len(bookmarks)} enriched={result.enriched} skipped={result.skipped} failed={result.failed}")
        return 0

    if args.cmd == "analyze" or args.cmd == "classify":
        from .analyzer import run_analysis
        if args.cmd == "classify":
            args.stage = "classify"
        result = run_analysis(store, stage=args.stage, provider=args.provider, changed_only=args.changed_only)
        print(f"analyzed={result['total']} classified={result['classified']} "
              f"entities_added={result['entities_added']} embedded={result['embedded']}")
        return 0

    if args.cmd == "entities":
        from .entities import extract_entities
        count = 0
        for row in store.list_bookmarks():
            bookmark_id = int(row["id"])
            links = [r["url"] for r in store.get_bookmark_links(bookmark_id)]
            text = (row["tweet_text"] or "") + "\n" + (row["raw_text"] or "")
            entity_tuples = extract_entities(text, links)
            for name, etype, source in entity_tuples:
                entity_id = store.upsert_entity(name, etype, source)
                if entity_id:
                    store.add_bookmark_entity(bookmark_id, entity_id)
            count += 1
        print(f"processed={count}")
        return 0

    if args.cmd == "embed":
        from .embeddings import embed_text
        count = 0
        for row in store.list_bookmarks():
            bookmark_id = int(row["id"])
            text = (row["tweet_text"] or "") + "\n" + (row["raw_text"] or "")
            vector, provider, model = embed_text(text, provider=args.provider)
            store.set_embedding(bookmark_id, vector, provider, model, row["content_hash"])
            count += 1
        print(f"embedded={count} provider={args.provider}")
        return 0

    if args.cmd == "cluster":
        from .clusters import generate_clusters
        result = generate_clusters(store, min_size=args.min_size, min_confidence=args.min_confidence)
        print(f"clusters_created={result['clusters_created']} bookmarks_clustered={result['bookmarks_clustered']}")
        return 0

    if args.cmd == "projects":
        from .projects import generate_projects
        result = generate_projects(store, min_evidence=args.min_evidence)
        print(f"projects_created={result['projects_created']} evidence_added={result['evidence_added']}")
        return 0

    if args.cmd == "export":
        return _cmd_export(args, store)

    if args.cmd == "review":
        return _cmd_review(args, store)

    if args.cmd == "graph":
        if args.graph_cmd == "export":
            export_graph_json(store, args.out)
            print(f"graph exported to {args.out}")
        return 0

    if args.cmd == "compress":
        return _cmd_compress(args, store)

    if args.cmd == "benchmark":
        return _cmd_benchmark(args, store)

    if args.cmd == "compact":
        return _cmd_compact(args, store)

    if args.cmd == "serve":
        store.close()
        ReviewServer(db_path).serve(args.host, args.port)
        return 0

    return 0


def _make_collector(store, args):
    config = load_config()
    browser_cfg = config.get("browser", {})
    return BrowserHarnessCollector(
        store,
        Checkpoint(),
        browser_app=args.browser_app or browser_cfg.get("app", "Google Chrome"),
        browser_profile=args.browser_profile or Path(browser_cfg.get("profile", "")),
        debug_port=args.debug_port or browser_cfg.get("debug_port", 9222),
    )


def _cmd_doctor(store, db_path: Path) -> int:
    import sys
    import platform

    print("=== tweetkb doctor ===")
    print(f"Python: {sys.version.split()[0]}")
    print(f"Platform: {platform.system()} {platform.release()}")
    print(f"Database: {db_path}")

    # Check db exists
    if db_path.exists():
        size = db_path.stat().st_size
        print(f"  DB size: {size:,} bytes ({size / 1024 / 1024:.1f} MB)")
    else:
        print("  WARNING: DB does not exist (run `tweetkb init`)")

    # Schema version
    try:
        version = store.schema_version()
        print(f"  Schema version: {version}")
    except Exception as e:
        print(f"  ERROR reading schema: {e}")

    # Bookmark count
    try:
        stats = store.stats()
        print(f"  Bookmarks: {stats['total']}")
        print(f"  Needs review: {stats['needs_review']}")
        print(f"  Categories: {len(stats['categories'])}")
    except Exception as e:
        print(f"  ERROR reading stats: {e}")

    # Page stats
    try:
        page_stats = store.page_stats()
        print(f"  Page size: {page_stats.get('page_size', '?')} bytes")
        print(f"  Page count: {page_stats.get('page_count', '?')}")
        print(f"  Free pages: {page_stats.get('freelist_count', '?')}")
    except Exception as e:
        print(f"  ERROR reading page stats: {e}")

    # Check browser harness
    import shutil
    if shutil.which("browser-harness"):
        print("  browser-harness: found")
    else:
        print("  WARNING: browser-harness not on PATH (collection unavailable)")

    # Check macOS
    if platform.system() == "Darwin":
        print("  macOS: detected (Apple Events available)")
        try:
            import subprocess
            result = subprocess.run(
                ["osascript", "-e", "tell application \"System Events\" to return name of processes"],
                capture_output=True, text=True, timeout=5
            )
            if "Google Chrome" in result.stdout:
                print("  Google Chrome: running")
        except Exception:
            pass

    return 0


def _cmd_export(args, store) -> int:
    vault_path = args.vault or Path(".")

    exclude_cats = {c.strip() for c in args.exclude_category.split(",") if c.strip()}
    include_cats = {c.strip() for c in args.include_category.split(",") if c.strip()} or None

    adapter = args.adapter

    if adapter == "obsidian":
        exported, skipped = export_obsidian(
            store, vault_path,
            include_categories=include_cats,
            exclude_categories=exclude_cats,
            exclude_review=args.exclude_review,
            min_confidence=args.min_confidence,
            include_projects=args.include_projects,
            include_clusters=args.include_clusters,
        )
    elif adapter == "logseq":
        exported, skipped = export_logseq(
            store, vault_path,
            include_categories=include_cats,
            exclude_categories=exclude_cats,
            exclude_review=args.exclude_review,
            min_confidence=args.min_confidence,
        )
    elif adapter == "markdown":
        exported, skipped = export_markdown(
            store, vault_path,
            include_categories=include_cats,
            exclude_categories=exclude_cats,
            exclude_review=args.exclude_review,
            min_confidence=args.min_confidence,
        )
    elif adapter == "jsonl":
        exported, skipped = export_jsonl(
            store, vault_path,
            include_categories=include_cats,
            exclude_categories=exclude_cats,
            exclude_review=args.exclude_review,
            min_confidence=args.min_confidence,
        )
    elif adapter == "csv":
        exported, skipped = export_csv(
            store, vault_path,
            include_categories=include_cats,
            exclude_categories=exclude_cats,
            exclude_review=args.exclude_review,
            min_confidence=args.min_confidence,
        )
    else:
        print(f"Unknown adapter: {adapter}")
        return 1

    store.log_export_run(adapter, str(vault_path), exported, skipped)
    print(f"exported={exported} skipped={skipped} adapter={adapter}")
    return 0


def _cmd_review(args, store) -> int:
    if args.review_cmd == "list":
        bookmarks = store.list_bookmarks(needs_review=True, category=args.category, limit=args.limit)
        print(f"=== Review Queue ({len(bookmarks)} bookmarks) ===")
        for row in bookmarks:
            text = (row["summary"] or row["tweet_text"] or "")[:80]
            print(f"  [{row['id']}] {row['status_id']} | {row['author_handle']} | {row['category'] if 'category' in row else '?'} | {text}")
        return 0

    if args.review_cmd == "approve":
        row = store.get_bookmark_by_status(args.status_id)
        if not row:
            print(f"Not found: {args.status_id}")
            return 1
        store.review_bookmark(int(row["id"]), "approved")
        print(f"approved {args.status_id}")
        return 0

    if args.review_cmd == "exclude":
        row = store.get_bookmark_by_status(args.status_id)
        if not row:
            print(f"Not found: {args.status_id}")
            return 1
        store.review_bookmark(int(row["id"]), "excluded")
        print(f"excluded {args.status_id}")
        return 0

    if args.review_cmd == "tag":
        row = store.get_bookmark_by_status(args.status_id)
        if not row:
            print(f"Not found: {args.status_id}")
            return 1
        store.add_tags(int(row["id"]), [args.tag])
        print(f"tagged {args.status_id} with #{args.tag}")
        return 0

    if args.review_cmd in ("junk", "open-junk"):
        from .junk import list_junk_candidates, open_bookmarks

        candidates = list_junk_candidates(store, limit=args.limit)
        print(f"=== Likely Junk ({len(candidates)} bookmarks) ===")
        for item in candidates:
            print(f"[{item.id}] {item.status_id} @{item.author_handle} | {item.reason} | {item.sample}")
            print(f"    {item.status_url}")
        if args.review_cmd == "open-junk":
            opened = open_bookmarks(
                [item.status_url for item in candidates],
                browser_app=getattr(args, "browser_app", None) or load_config().get("browser", {}).get("app", "Google Chrome"),
            )
            print(f"opened={opened}")
        return 0

    return 0


def _cmd_compress(args, store) -> int:
    from .compress import (
        inspect_archive,
        encode_file, decode_file, verify_archive,
    )

    if args.compress_cmd == "benchmark":
        return _benchmark_compress(store)

    if args.compress_cmd == "export":
        # Export bookmarks as JSONL first, then compress
        records = []
        for row in store.list_bookmarks():
            records.append({
                "status_id": str(row["status_id"]),
                "status_url": row["status_url"],
                "author_handle": row["author_handle"],
                "author_name": row["author_name"],
                "tweet_text": row["tweet_text"],
                "raw_text": row["raw_text"],
            })

        import tempfile
        import json
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False, mode="w") as f:
            for r in records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
            tmp_path = Path(f.name)

        encode_file(tmp_path, args.out)
        tmp_path.unlink()

        orig_size = sum(len(json.dumps(r)) for r in records)
        compressed_size = args.out.stat().st_size
        ratio = orig_size / compressed_size if compressed_size > 0 else 0
        print(f"compressed={len(records)} records out={args.out} ratio={ratio:.2f}x")
        return 0

    if args.compress_cmd == "decompress":
        decode_file(args.input, args.out)
        print(f"decompressed {args.input} -> {args.out}")
        return 0

    if args.compress_cmd == "inspect":
        data = args.input.read_bytes()
        info = inspect_archive(data)
        print(json.dumps(info, indent=2))
        return 0

    if args.compress_cmd == "verify":
        ok = verify_archive(args.input)
        if ok:
            print(f"OK: {args.input}")
        else:
            print(f"INVALID: {args.input}")
        return 0 if ok else 1

    return 0


def _benchmark_compress(store) -> int:
    import time
    import tempfile
    import json
    import gzip
    from .compress import encode_records, decode_records

    # Collect records
    records = []
    for row in store.list_bookmarks(limit=1000):
        records.append({
            "status_id": str(row["status_id"]),
            "status_url": row["status_url"],
            "author_handle": row["author_handle"],
            "author_name": row["author_name"],
            "tweet_text": row["tweet_text"],
        })

    if not records:
        print("No bookmarks to benchmark")
        return 1

    # JSONL baseline
    jsonl_bytes = sum(len(json.dumps(r)) for r in records)
    jsonl_file = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
    with open(jsonl_file.name, "w") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    jsonl_file_size = Path(jsonl_file.name).stat().st_size

    # Gzip baseline
    with tempfile.NamedTemporaryFile(suffix=".gz", delete=False) as gf:
        gz_path = gf.name
    with gzip.open(gz_path, "wb") as f:
        for r in records:
            f.write((json.dumps(r, ensure_ascii=False) + "\n").encode())
    gzip_size = Path(gz_path).stat().st_size

    # TweetZip
    start = time.perf_counter()
    twz_data = encode_records(records)
    encode_ms = (time.perf_counter() - start) * 1000

    start = time.perf_counter()
    decoded = decode_records(twz_data)
    decode_ms = (time.perf_counter() - start) * 1000

    twz_size = len(twz_data)
    ratio = jsonl_bytes / twz_size if twz_size > 0 else 0

    print(f"=== Compression Benchmark ({len(records)} records) ===")
    print(f"JSONL bytes:     {jsonl_bytes:,}")
    print(f"JSONL file:      {jsonl_file_size:,}")
    print(f"Gzip JSONL:      {gzip_size:,} ({gzip_size/jsonl_file_size:.2f}x)")
    print(f"TweetZip:        {twz_size:,} ({ratio:.2f}x vs JSONL)")
    print(f"Encode:          {encode_ms:.1f}ms ({len(records)/(encode_ms/1000):.0f} records/s)")
    print(f"Decode:          {decode_ms:.1f}ms ({len(records)/(decode_ms/1000):.0f} records/s)")
    print(f"Roundtrip OK:    {len(decoded) == len(records)}")

    # Cleanup
    Path(jsonl_file.name).unlink()
    Path(gz_path).unlink()

    return 0


def _cmd_benchmark(args, store) -> int:
    import time

    if args.stage in ("all", "analyze"):
        from .analyzer import run_analysis
        start = time.perf_counter()
        run_analysis(store, stage="all", changed_only=False)
        elapsed = time.perf_counter() - start
        bookmarks = store.conn.execute("SELECT count(*) FROM bookmarks WHERE is_deleted = 0").fetchone()[0]
        print(f"analyze: {elapsed:.2f}s for {bookmarks} bookmarks ({bookmarks/elapsed:.0f}/s)")

    if args.stage in ("all", "export"):
        from .exporters.obsidian import export_obsidian
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            start = time.perf_counter()
            export_obsidian(store, Path(tmpdir))
            elapsed = time.perf_counter() - start
            bookmarks = store.conn.execute("SELECT count(*) FROM bookmarks WHERE is_deleted = 0").fetchone()[0]
            print(f"export (obsidian): {elapsed:.2f}s for {bookmarks} bookmarks ({bookmarks/elapsed:.0f}/s)")

    if args.stage in ("all", "compress"):
        from .compress import encode_records, decode_records
        records = [{"status_id": str(r["status_id"]), "tweet_text": r["tweet_text"] or ""}
                   for r in store.list_bookmarks()]
        if records:
            start = time.perf_counter()
            data = encode_records(records)
            encode_ms = (time.perf_counter() - start) * 1000
            start = time.perf_counter()
            decode_records(data)
            decode_ms = (time.perf_counter() - start) * 1000
            print(f"compress: encode={encode_ms:.0f}ms decode={decode_ms:.0f}ms ({len(records)} records)")

    return 0


def _cmd_compact(args, store) -> int:
    stats = store.page_stats()
    print("=== Database Compact Report ===")
    print(f"Path:        {stats['database_path']}")
    print(f"File size:  {stats['file_size_bytes']:,} bytes ({stats['file_size_bytes']/1024/1024:.2f} MB)")
    print(f"Page size:  {stats['page_size']} bytes")
    print(f"Pages:      {stats['page_count']}")
    print(f"Free pages: {stats['freelist_count']}")
    print(f"Reclaimable: {stats.get('estimated_reclaimable_bytes', 0):,} bytes")
    print(f"Bookmarks:  {stats['bookmark_count']}")
    print(f"Links:      {stats['link_count']}")
    print(f"Entities:   {stats['entity_count']}")
    print(f"Embeddings: {stats['embedding_count']}")

    if args.backup:
        import shutil
        db_path = Path(store.path)
        shutil.copy2(db_path, args.backup)
        print(f"\nBacked up to {args.backup}")

    if not args.dry_run and stats.get("freelist_count", 0) > 0:
        print("\nRunning VACUUM...")
        store.vacuum()
        new_stats = store.page_stats()
        print(f"New file size: {new_stats['file_size_bytes']:,} bytes")
        print(f"Freed ~{stats['file_size_bytes'] - new_stats['file_size_bytes']:,} bytes")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
