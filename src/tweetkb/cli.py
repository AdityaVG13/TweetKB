from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path

from .checkpoint import Checkpoint
from .collector import BrowserHarnessCollector
from .config import load_config
from .db import DEFAULT_DB
from .db import Store as DBStore
from .exporters import ADAPTERS
from .exporters.csv import export_csv
from .exporters.jsonl import export_jsonl
from .exporters.logseq import export_logseq
from .exporters.markdown import export_markdown
from .exporters.obsidian import export_obsidian
from .exporters.spec import export_spec
from .graph import export_graph_json
from .server import ReviewServer


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        try:
            return _interactive_menu()
        except KeyboardInterrupt:
            print("\nInterrupted.", file=sys.stderr)
            return 130

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
    collect.add_argument(
        "--stop-at-existing",
        action="store_true",
        default=True,
        help="When collecting --all, stop after reaching already-saved bookmark history.",
    )
    collect.add_argument(
        "--no-stop-at-existing",
        dest="stop_at_existing",
        action="store_false",
        help="When collecting --all, rescan the whole bookmark timeline.",
    )

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
    enrich.add_argument("--include-media", action="store_true", help="Analyze images attached to the bookmarked post")
    enrich.add_argument("--max-media", type=int, default=4, help="Max images to analyze per bookmark")
    enrich.add_argument("--vision-provider", default="openai", choices=["openai", "ollama", "metadata"])
    enrich.add_argument("--vision-model", default=None, help="Vision model override")
    enrich.add_argument("--vision-detail", default="auto", choices=["low", "auto", "high"])
    enrich.add_argument(
        "--include-conversation",
        default="auto",
        choices=["auto", "always", "never"],
        help="Capture visible thread/reply context. auto captures it for question bookmarks.",
    )
    enrich.add_argument("--max-conversation-items", type=int, default=12, help="Max thread/reply items to store")

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
    analyze.add_argument("--include-category", default="", help="Analyze only already-classified categories")
    analyze.add_argument("--exclude-category", default="", help="Skip already-classified categories")
    analyze.add_argument("--needs-review", action="store_true", default=None, help="Analyze only bookmarks needing review")
    analyze.add_argument("--reviewed", dest="needs_review", action="store_false", help="Analyze only reviewed bookmarks")
    analyze.add_argument("--review-state", default=None, help="Analyze only one review state")
    analyze.add_argument("--limit", type=int, default=None, help="Analyze at most N selected bookmarks")

    # analyze-export
    analyze_export = sub.add_parser("analyze-export", help="Run analysis, then export to a selected folder")
    analyze_export.add_argument("--stage", default="all", choices=["all", "classify", "entities", "embed"])
    analyze_export.add_argument("--provider", default="local-hash", choices=["local-hash", "ollama", "openai"])
    analyze_export.add_argument("--changed-only", action="store_true", default=True)
    analyze_export.add_argument("--no-changed-only", dest="changed_only", action="store_false")
    analyze_export.add_argument("--include-category", default="", help="Analyze/export only selected categories")
    analyze_export.add_argument("--exclude-category", default="", help="Skip selected categories")
    analyze_export.add_argument("--needs-review", action="store_true", default=None, help="Analyze/export only rows needing review")
    analyze_export.add_argument("--reviewed", dest="needs_review", action="store_false", help="Analyze/export only reviewed rows")
    analyze_export.add_argument("--review-state", default=None, help="Analyze only one review state")
    analyze_export.add_argument("--limit", type=int, default=None, help="Analyze at most N selected bookmarks")
    analyze_export.add_argument("--adapter", "-a", default="spec", choices=list(ADAPTERS.keys()))
    analyze_export.add_argument("--vault", "--out", "-o", type=Path, required=False)
    analyze_export.add_argument("--exclude-review", action="store_true")
    analyze_export.add_argument("--min-confidence", type=float, default=0.0)
    analyze_export.add_argument("--include-projects", action="store_true", default=True)
    analyze_export.add_argument("--include-clusters", action="store_true", default=False)

    # classify (legacy, delegates to analyze)
    classify = sub.add_parser("classify", help="Classify bookmarks (alias for analyze --stage classify)")
    classify.add_argument("--include-category", default="", help="Classify only already-classified categories")
    classify.add_argument("--exclude-category", default="", help="Skip already-classified categories")
    classify.add_argument("--needs-review", action="store_true", default=None, help="Classify only bookmarks needing review")
    classify.add_argument("--reviewed", dest="needs_review", action="store_false", help="Classify only reviewed bookmarks")
    classify.add_argument("--review-state", default=None, help="Classify only one review state")
    classify.add_argument("--limit", type=int, default=None, help="Classify at most N selected bookmarks")

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

    media_export = sub.add_parser("media-export", help="Export captured tweet images for manual AI review")
    media_export.add_argument("--out", "-o", type=Path, default=Path("exports/media-review"))
    media_export.add_argument("--limit", type=int, default=None)
    media_export.add_argument("--manifest-only", action="store_true", help="Write manifest and prompt without downloading images")

    release_audit = sub.add_parser("release-audit", help="Scan tracked files for public-release blockers")
    release_audit.add_argument("--strict-worktree", action="store_true", help="Also fail on ignored local data files")

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

    if args.cmd == "release-audit":
        return _cmd_release_audit(args)

    # Resolve db path
    db_path = args.db or load_config().get("database", {}).get("path", str(DEFAULT_DB))
    db_path = Path(db_path)

    try:
        return _dispatch(args, db_path)
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if "--debug" in sys.argv:
            raise
        return 1


def _interactive_menu() -> int:
    print("TweetKB")
    print("Local bookmark knowledge base")
    while True:
        print(
            "\n".join(
                [
                    "",
                    "1. Initialize database",
                    "2. Open login browser",
                    "3. Collect bookmarks",
                    "4. Enrich saved bookmarks",
                    "5. Analyze bookmarks",
                    "5a. Analyze + export to folder",
                    "6. Export",
                    "7. Review",
                    "8. Stats",
                    "9. Generate clusters",
                    "10. Generate project ideas",
                    "11. Export graph",
                    "12. TweetZip compression",
                    "13. Start review UI",
                    "14. Doctor",
                    "15. Release audit",
                    "16. Run custom command",
                    "17. Export media review bundle",
                    "0. Quit",
                ]
            )
        )
        choice = input("Select: ").strip().lower()
        if choice in {"0", "q", "quit", "exit"}:
            return 0
        command = _interactive_command_for_choice(choice)
        if command is None:
            print("Unknown selection.")
            continue
        if not command:
            continue
        print(f"$ tweetkb {' '.join(shlex.quote(part) for part in command)}")
        code = main(command)
        if code == 130:
            return 130
        if code:
            print(f"Command exited with status {code}.")


def _interactive_command_for_choice(choice: str, input_fn=input) -> list[str] | None:
    if choice == "1":
        return ["init"]
    if choice == "2":
        command = ["login"]
        if _prompt_bool("Use normal Chrome profile?", default=False, input_fn=input_fn):
            command.append("--normal-chrome")
        return command
    if choice == "3":
        command = ["collect"]
        mode = _prompt_choice(
            "Collection mode",
            ["apple-events", "normal-chrome", "browser-harness"],
            default="apple-events",
            input_fn=input_fn,
        )
        if mode == "normal-chrome":
            command.extend(["--normal-chrome", "--existing-tab"])
        elif mode == "apple-events":
            command.append("--apple-events")
        if _prompt_bool("Collect all bookmarks?", default=False, input_fn=input_fn):
            command.append("--all")
        else:
            command.extend(["--limit", str(_prompt_int("Limit", 100, input_fn))])
        command.extend(["--batch-size", str(_prompt_int("Batch size", 20, input_fn))])
        command.extend(["--wait", str(_prompt_float("Wait seconds", 1.5, input_fn))])
        return command
    if choice in {"4", "enrich"}:
        command = ["enrich", "--apple-events"]
        _append_optional_arg(command, "--category", _prompt_text("Category", "", input_fn))
        _append_optional_arg(command, "--since", _prompt_text("Since YYYY-MM-DD", "", input_fn))
        command.extend(["--limit", str(_prompt_int("Limit", 25, input_fn))])
        command.extend(["--wait", str(_prompt_float("Wait seconds", 2.0, input_fn))])
        conversation = _prompt_choice(
            "Thread/reply context",
            ["auto", "always", "never"],
            "auto",
            input_fn,
        )
        command.extend(["--include-conversation", conversation])
        if conversation != "never":
            command.extend(["--max-conversation-items", str(_prompt_int("Max thread/reply items", 12, input_fn))])
        if _prompt_bool("Include outbound links?", default=False, input_fn=input_fn):
            command.append("--include-links")
            command.extend(["--max-links", str(_prompt_int("Max links", 3, input_fn))])
        if _prompt_bool("Analyze media images?", default=False, input_fn=input_fn):
            command.append("--include-media")
            provider = _prompt_choice("Vision provider", ["openai", "ollama", "metadata"], "openai", input_fn)
            command.extend(["--vision-provider", provider])
            _append_optional_arg(command, "--vision-model", _prompt_text("Vision model", "", input_fn))
            command.extend(["--max-media", str(_prompt_int("Max images", 4, input_fn))])
        if _prompt_bool("Re-enrich existing rows?", default=False, input_fn=input_fn):
            command.append("--all")
        return command
    if choice in {"5", "analyze"}:
        command = ["analyze"]
        _append_interactive_analysis_args(command, input_fn)
        return command
    if choice in {"5a", "5e", "4a", "4e", "ae", "analyze-export"}:
        command = ["analyze-export"]
        _append_interactive_analysis_args(command, input_fn, default_stage="all")
        _append_interactive_export_args(command, input_fn, default_adapter="spec")
        return command
    if choice == "6":
        command = ["export"]
        _append_interactive_export_args(command, input_fn)
        return command
    if choice == "7":
        action = _prompt_choice("Review action", ["list", "junk", "open-junk", "approve", "exclude", "tag"], "list", input_fn)
        command = ["review", action]
        if action in {"list", "junk", "open-junk"}:
            if action == "list":
                _append_optional_arg(command, "--category", _prompt_text("Category", "", input_fn))
            command.extend(["--limit", str(_prompt_int("Limit", 50 if action != "open-junk" else 10, input_fn))])
        elif action in {"approve", "exclude"}:
            command.append(_prompt_text("Status ID", "", input_fn))
        elif action == "tag":
            command.append(_prompt_text("Status ID", "", input_fn))
            command.append(_prompt_text("Tag", "", input_fn))
        return command
    if choice == "8":
        return ["stats"]
    if choice == "9":
        return [
            "cluster",
            "--min-size",
            str(_prompt_int("Min size", 3, input_fn)),
            "--min-confidence",
            str(_prompt_float("Min confidence", 0.4, input_fn)),
        ]
    if choice == "10":
        return ["projects", "--min-evidence", str(_prompt_int("Min evidence", 3, input_fn))]
    if choice == "11":
        return ["graph", "export", "--out", _prompt_text("Output path", "exports/graph.json", input_fn)]
    if choice == "12":
        action = _prompt_choice("Compression action", ["benchmark", "export", "verify", "inspect", "decompress"], "benchmark", input_fn)
        command = ["compress", action]
        if action == "export":
            command.extend(["--out", _prompt_text("Output .twz", "exports/bookmarks.twz", input_fn)])
        elif action in {"verify", "inspect"}:
            command.append(_prompt_text("Input .twz", "exports/bookmarks.twz", input_fn))
        elif action == "decompress":
            command.append(_prompt_text("Input .twz", "exports/bookmarks.twz", input_fn))
            command.extend(["--out", _prompt_text("Output JSONL", "exports/bookmarks.jsonl", input_fn)])
        return command
    if choice == "13":
        return [
            "serve",
            "--host",
            _prompt_text("Host", "127.0.0.1", input_fn),
            "--port",
            str(_prompt_int("Port", 8765, input_fn)),
        ]
    if choice == "14":
        return ["doctor"]
    if choice == "15":
        command = ["release-audit"]
        if _prompt_bool("Strict worktree scan?", default=False, input_fn=input_fn):
            command.append("--strict-worktree")
        return command
    if choice == "16":
        raw = _prompt_text("Command after `tweetkb`", "", input_fn)
        return shlex.split(raw) if raw else []
    if choice == "17":
        command = ["media-export", "--out", _prompt_text("Output folder", "exports/media-review", input_fn)]
        limit = _prompt_text("Limit", "", input_fn)
        if limit:
            command.extend(["--limit", limit])
        if _prompt_bool("Manifest only?", default=False, input_fn=input_fn):
            command.append("--manifest-only")
        return command
    return None


def _append_interactive_analysis_args(command: list[str], input_fn=input, default_stage: str = "classify") -> None:
    stage = _prompt_choice("Stage", ["classify", "all", "entities", "embed"], default=default_stage, input_fn=input_fn)
    command.extend(["--stage", stage])
    if stage in {"all", "embed"}:
        provider = _prompt_choice("Embedding provider", ["local-hash", "ollama", "openai"], "local-hash", input_fn)
        command.extend(["--provider", provider])
    if not _prompt_bool("Changed only?", default=True, input_fn=input_fn):
        command.append("--no-changed-only")
    _append_optional_arg(command, "--include-category", _prompt_text("Include categories CSV", "", input_fn))
    _append_optional_arg(command, "--exclude-category", _prompt_text("Exclude categories CSV", "", input_fn))
    review_filter = _prompt_choice("Review filter", ["any", "needs-review", "reviewed"], "any", input_fn)
    if review_filter == "needs-review":
        command.append("--needs-review")
    elif review_filter == "reviewed":
        command.append("--reviewed")
    _append_optional_arg(command, "--review-state", _prompt_text("Review state", "", input_fn))
    limit = _prompt_text("Limit", "", input_fn)
    if limit:
        command.extend(["--limit", limit])


def _append_interactive_export_args(command: list[str], input_fn=input, default_adapter: str = "obsidian") -> None:
    adapter = _prompt_choice("Adapter", sorted(ADAPTERS.keys()), default_adapter, input_fn)
    command.extend(["--adapter", adapter])
    default_out = "./obsidian-vault" if adapter == "obsidian" else f"./exports/{adapter}"
    command.extend(["--vault", _prompt_text("Output folder", default_out, input_fn)])
    if command[0] == "export":
        _append_optional_arg(command, "--include-category", _prompt_text("Include categories CSV", "", input_fn))
        _append_optional_arg(command, "--exclude-category", _prompt_text("Exclude categories CSV", "", input_fn))
    if _prompt_bool("Exclude needs-review rows?", default=False, input_fn=input_fn):
        command.append("--exclude-review")
    min_confidence = _prompt_text("Min confidence", "", input_fn)
    if min_confidence:
        command.extend(["--min-confidence", min_confidence])


def _prompt_text(prompt: str, default: str, input_fn=input) -> str:
    suffix = f" [{default}]" if default else ""
    value = input_fn(f"{prompt}{suffix}: ").strip()
    return value or default


def _prompt_int(prompt: str, default: int, input_fn=input) -> int:
    while True:
        value = _prompt_text(prompt, str(default), input_fn)
        try:
            return int(value)
        except ValueError:
            print("Enter a whole number.")


def _prompt_float(prompt: str, default: float, input_fn=input) -> float:
    while True:
        value = _prompt_text(prompt, str(default), input_fn)
        try:
            return float(value)
        except ValueError:
            print("Enter a number.")


def _prompt_bool(prompt: str, default: bool, input_fn=input) -> bool:
    default_text = "Y/n" if default else "y/N"
    while True:
        value = input_fn(f"{prompt} [{default_text}]: ").strip().lower()
        if not value:
            return default
        if value in {"y", "yes"}:
            return True
        if value in {"n", "no"}:
            return False
        print("Enter yes or no.")


def _prompt_choice(prompt: str, choices: list[str], default: str, input_fn=input) -> str:
    choice_text = "/".join(choices)
    while True:
        value = input_fn(f"{prompt} ({choice_text}) [{default}]: ").strip()
        value = value or default
        if value in choices:
            return value
        print(f"Choose one of: {choice_text}")


def _append_optional_arg(command: list[str], flag: str, value: str) -> None:
    if value:
        command.extend([flag, value])


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
        collect_limit = None if args.all else args.limit
        mode = "apple-events" if args.apple_events else "normal-chrome" if args.normal_chrome else "browser-harness"
        print(
            f"collect: limit={'all' if collect_limit is None else collect_limit} "
            f"batch_size={args.batch_size} wait={args.wait} mode={mode}",
            flush=True,
        )
        if mode == "browser-harness":
            print("browser-harness: using local managed Chrome; no AI model or cloud API is used.", flush=True)
        if args.all and args.stop_at_existing:
            print(
                "collect: will stop once already-saved bookmark history is reached "
                "(use --no-stop-at-existing to rescan everything).",
                flush=True,
            )
        result = collector.collect(
            collect_limit,
            args.batch_size,
            args.wait,
            existing_tab=args.existing_tab,
            normal_chrome=args.normal_chrome,
            apple_events=args.apple_events,
            all_bookmarks=args.all,
            stop_at_existing=args.stop_at_existing,
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
            missing_source_type="image-analysis" if args.include_media else None,
        )
        target = "image-analysis" if args.include_media else "text/article"
        mode = "missing" if not args.all else "all matching"
        print(
            f"enrich: selecting {len(bookmarks)} {mode} {target} bookmarks "
            f"newest collected/bookmark-page order first",
            flush=True,
        )
        for row in bookmarks[:5]:
            text = " ".join((row["tweet_text"] or row["raw_text"] or "").split())[:90]
            print(f"enrich: queued {row['status_id']} {row['status_url']} {text}", flush=True)
        if len(bookmarks) > 5:
            print(f"enrich: ... {len(bookmarks) - 5} more queued", flush=True)
        result = enrich_with_apple_events(
            store,
            bookmarks,
            browser_app=args.browser_app or load_config().get("browser", {}).get("app", "Google Chrome"),
            wait_seconds=args.wait,
            include_links=args.include_links,
            max_links=args.max_links,
            include_media=args.include_media,
            max_media=args.max_media,
            vision_provider=args.vision_provider,
            vision_model=args.vision_model,
            vision_detail=args.vision_detail,
            include_conversation=args.include_conversation,
            max_conversation_items=args.max_conversation_items,
            progress=_print_progress,
        )
        print(
            f"selected={len(bookmarks)} enriched={result.enriched} conversations={result.conversations} "
            f"media_analyzed={result.media_analyzed} skipped={result.skipped} failed={result.failed}"
        )
        return 0

    if args.cmd == "analyze" or args.cmd == "classify":
        if args.cmd == "classify":
            args.stage = "classify"
            args.provider = "local-hash"
            args.changed_only = False
        _print_analysis_result(_run_analysis(args, store))
        return 0

    if args.cmd == "analyze-export":
        _print_analysis_result(_run_analysis(args, store))
        export_code = _cmd_export(args, store)
        if export_code == 0:
            print(f"analysis export folder={args.vault or Path('.')}")
        return export_code

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

    if args.cmd == "media-export":
        from .media_export import export_media_bundle

        result = export_media_bundle(
            store,
            args.out,
            limit=args.limit,
            download=not args.manifest_only,
        )
        print(
            f"tweets={result.tweets} images={result.images} downloaded={result.downloaded} "
            f"failed={result.failed} out={result.out_dir}"
        )
        return 0

    if args.cmd == "serve":
        store.close()
        ReviewServer(db_path).serve(args.host, args.port)
        return 0

    return 0


def _run_analysis(args, store) -> dict:
    from .analyzer import run_analysis

    include_cats = _parse_csv_set(args.include_category) or None
    exclude_cats = _parse_csv_set(args.exclude_category) or None
    return run_analysis(
        store,
        stage=args.stage,
        provider=args.provider,
        changed_only=args.changed_only,
        include_categories=include_cats,
        exclude_categories=exclude_cats,
        needs_review=args.needs_review,
        review_state=args.review_state,
        limit=args.limit,
        progress=_print_progress,
    )


def _print_analysis_result(result: dict) -> None:
    print(
        f"selected={result['selected']} analyzed={result['total']} classified={result['classified']} "
        f"entities_added={result['entities_added']} embedded={result['embedded']}"
    )


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
    import platform
    import sys

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


def _cmd_release_audit(args) -> int:
    from .release_audit import audit_repository, format_violations

    root = Path.cwd()
    violations = audit_repository(root, strict_worktree=args.strict_worktree)
    if violations:
        print(format_violations(violations), file=sys.stderr)
        return 1
    print("release audit passed")
    return 0


def _cmd_export(args, store) -> int:
    vault_path = args.vault or Path(".")

    exclude_cats = _parse_csv_set(args.exclude_category)
    include_cats = _parse_csv_set(args.include_category) or None

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
    elif adapter == "spec":
        exported, skipped = export_spec(
            store, vault_path,
            include_categories=include_cats,
            exclude_categories=exclude_cats,
            exclude_review=args.exclude_review,
            min_confidence=args.min_confidence,
            include_projects=args.include_projects,
            include_clusters=args.include_clusters,
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


def _parse_csv_set(value: str | None) -> set[str]:
    return {item.strip() for item in (value or "").split(",") if item.strip()}


def _print_progress(message: str) -> None:
    print(message, flush=True)


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
        decode_file,
        encode_file,
        inspect_archive,
        verify_archive,
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

        import json
        import tempfile
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
    import gzip
    import json
    import tempfile
    import time

    from .compress import decode_records, encode_records

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
        import tempfile

        from .exporters.obsidian import export_obsidian
        with tempfile.TemporaryDirectory() as tmpdir:
            start = time.perf_counter()
            export_obsidian(store, Path(tmpdir))
            elapsed = time.perf_counter() - start
            bookmarks = store.conn.execute("SELECT count(*) FROM bookmarks WHERE is_deleted = 0").fetchone()[0]
            print(f"export (obsidian): {elapsed:.2f}s for {bookmarks} bookmarks ({bookmarks/elapsed:.0f}/s)")

    if args.stage in ("all", "compress"):
        from .compress import decode_records, encode_records
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
