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
    argv = sys.argv[1:] if argv is None else list(argv)
    if not argv:
        from .agent import USAGE

        print(USAGE, end="" if USAGE.endswith("\n") else "\n")
        return 0

    rewritten = _rewrite_argv(argv)
    if rewritten is None:
        return 2
    argv = rewritten

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
    collect.add_argument(
        "--headless",
        action="store_true",
        help="Collect in a background Chrome using a copy of the logged-in profile. Does not restart your daily Chrome.",
    )
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
    collect.add_argument(
        "--stop-after-known",
        type=int,
        default=8,
        help="Stop after this many already-saved tweets in a row at the older end of the timeline. Ignores re-bookmarked tweets at the top.",
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

    search = sub.add_parser("search", help="Search bookmarks (offline FTS)")
    search.add_argument("query", nargs="*", help="Search query. Also accepts from:handle and cat:slug")
    search.add_argument("--from", dest="from_handle", default=None, help="Author handle, without @")
    search.add_argument("--category", default=None, help="Primary category slug")
    search.add_argument("--domain", default=None, help="Outbound link domain, e.g. github.com")
    search.add_argument("--sort", default="rank", choices=["rank", "saved", "posted"], help="rank, saved (bookmark time), or posted (tweet time)")
    search.add_argument("--saved-after", default=None, help="Only bookmarks captured on/after ISO date")
    search.add_argument("--json", action="store_true", dest="as_json", help="Write {\"hits\":[...]} to stdout")
    search.add_argument("--open", nargs="?", const=1, type=int, dest="open_count", help="Open the top N tweet URLs")
    search.add_argument("--limit", type=int, default=50)

    sub.add_parser("tui", help="Instrument-panel TUI (search, meters, mermaid graph)")
    sub.add_parser("wizard", help="Numbered command menu")
    cap = sub.add_parser("capabilities", help="Print the machine-readable CLI contract")
    cap.add_argument("--json", action="store_true", dest="as_json", help="Always JSON; flag accepted for agents")
    sub.add_parser("agent-guide", help="Print a paste-ready handbook for agents")
    nxt = sub.add_parser("next", help="One-shot triage: counts, categories, next commands")
    nxt.add_argument("--json", action="store_true", dest="as_json")

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
    bench.add_argument("--stage", default="all", choices=["all", "analyze", "export"])

    # compact
    compact = sub.add_parser("compact", help="Database maintenance")
    compact.add_argument("--vacuum", action="store_true", help="Run VACUUM after stats")
    compact.add_argument("--dry-run", action="store_true", help="Show stats without vacuuming")
    compact.add_argument("--backup", type=Path, default=None, help="Backup path")

    # stats
    sub.add_parser("stats", help="Show database statistics")
    digest = sub.add_parser("digest", help="Aggregate categories, domains, and authors")
    digest.add_argument("--json", action="store_true", dest="as_json")
    digest.add_argument("--saved-after", default=None, help="Only bookmarks captured on/after ISO date")
    digest.add_argument("--limit", type=int, default=20)
    related = sub.add_parser("related", help="Bookmarks connected by url, domain, or author")
    related.add_argument("status_id", help="Status ID of the center tweet")
    related.add_argument("--kinds", default="url,domain,author", help="url, domain, author, cat")
    related.add_argument("--json", action="store_true", dest="as_json")
    related.add_argument("--limit", type=int, default=20)
    mapped = sub.add_parser("map", help="ASCII geography for one author")
    mapped.add_argument("--from", dest="from_handle", required=True, help="Author handle, without @")
    mapped.add_argument("--json", action="store_true", dest="as_json")
    mapped.add_argument("--limit", type=int, default=20)
    atlas = sub.add_parser("atlas", help="Write a static local map of categories/domains/authors")
    atlas.add_argument("--out", "-o", type=Path, default=Path("exports/atlas.html"))
    atlas.add_argument("--open", action="store_true", dest="open_atlas")
    atlas.add_argument("--limit", type=int, default=20)
    sub.add_parser("repair-links", help="Rebuild outbound URLs from stored tweet text (no browser)")

    unbookmark = sub.add_parser("unbookmark", help="Remove selected tweets from X bookmarks; keep local copies")
    unbookmark.add_argument("--search", default="", help="List matching bookmarks to select")
    unbookmark.add_argument("--ids", nargs="+", default=[], help="Status IDs to unbookmark on X")
    unbookmark.add_argument("--yes", action="store_true", help="Required to actually click unbookmark on X")
    unbookmark.add_argument("--json", action="store_true", dest="as_json")
    unbookmark.add_argument("--limit", type=int, default=50)

    # serve
    serve = sub.add_parser("serve", help="Start the review UI server")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)

    args = parser.parse_args(argv)

    if args.cmd == "release-audit":
        return _cmd_release_audit(args)
    if args.cmd == "capabilities":
        from .agent import capabilities_json

        print(capabilities_json(), end="")
        return 0
    if args.cmd == "agent-guide":
        from .agent import AGENT_GUIDE

        print(AGENT_GUIDE)
        return 0
    if args.cmd == "wizard":
        try:
            return _interactive_menu()
        except KeyboardInterrupt:
            print("\nInterrupted.", file=sys.stderr)
            return 130

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
    print("Local bookmark knowledge base — offline, no LLM")
    while True:
        print(
            "\n".join(
                [
                    "",
                    "1. Collect bookmarks",
                    "2. Search",
                    "3. Analyze (offline)",
                    "4. Stats",
                    "5. Export",
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
    if choice in {"2", "12", "search"}:
        query = _prompt_text("Search query", "", input_fn)
        command = ["search", query] if query else ["search"]
        command.extend(["--limit", str(_prompt_int("Limit", 50, input_fn))])
        return command
    if choice == "enrich":
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
    if choice in {"3", "analyze"}:
        command = ["analyze"]
        _append_interactive_analysis_args(command, input_fn)
        return command
    if choice in {"5a", "5e", "4a", "4e", "ae", "analyze-export"}:
        command = ["analyze-export"]
        _append_interactive_analysis_args(command, input_fn, default_stage="all")
        _append_interactive_export_args(command, input_fn, default_adapter="spec")
        return command
    if choice in {"5", "6"}:
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
    if choice in {"4", "8"}:
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
        query = _prompt_text("Search query", "", input_fn)
        command = ["search", query] if query else ["search"]
        command.extend(["--limit", str(_prompt_int("Limit", 50, input_fn))])
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
    create = args.cmd in {"init", "migrate"}
    store = DBStore(db_path, create=create)

    if args.cmd == "init":
        store.init()
        print(f"initialized {db_path}")
        print(f"schema version: {store.schema_version()}")
        return 0

    if args.cmd == "migrate":
        store.init()
        print(f"schema version: {store.schema_version()}")
        return 0

    store.init()

    if args.cmd == "doctor":
        return _cmd_doctor(store, db_path)

    if args.cmd == "stats":
        print(json.dumps(store.stats(), indent=2))
        return 0

    if args.cmd == "digest":
        from .digest import build_digest, format_digest

        payload = build_digest(store, saved_after=getattr(args, "saved_after", None), limit=getattr(args, "limit", 20) or 20)
        if getattr(args, "as_json", False):
            print(json.dumps(payload, indent=2))
        else:
            print(format_digest(payload))
        return 0

    if args.cmd == "tui":
        return _cmd_tui(store)

    if args.cmd == "related":
        return _cmd_related(args, store)

    if args.cmd == "map":
        return _cmd_map(args, store)

    if args.cmd == "atlas":
        return _cmd_atlas(args, store)

    if args.cmd in {"search", "find"}:
        return _cmd_search(args, store)

    if args.cmd == "unbookmark":
        return _cmd_unbookmark(args, store)

    if args.cmd == "repair-links":
        from .normalize import repair_links_from_text

        result = repair_links_from_text(store)
        print(f"bookmarks={result['bookmarks']} urls={result['urls']}")
        return 0

    if args.cmd == "next":
        from .agent import next_payload

        payload = next_payload(store.stats())
        print(json.dumps(payload, indent=2))
        return 0

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
        if not args.normal_chrome and not args.apple_events and not args.headless and sys.platform == "darwin":
            args.apple_events = True
        collector = _make_collector(store, args)
        if not args.apple_events and not args.headless:
            collector.ensure_available()
        collect_limit = None if args.all else args.limit
        if args.headless:
            mode = "headless"
        elif args.apple_events:
            mode = "apple-events"
        elif args.normal_chrome:
            mode = "normal-chrome"
        else:
            mode = "browser-harness"
        print(
            f"collect: limit={'all' if collect_limit is None else collect_limit} "
            f"batch_size={args.batch_size} wait={args.wait} mode={mode}",
            flush=True,
        )
        if mode == "browser-harness":
            print("browser-harness: using local managed Chrome; no AI model or cloud API is used.", flush=True)
        if mode == "apple-events":
            print("apple-events: using your already-running Chrome. No remote debugging, no Chrome restart.", flush=True)
        if mode == "headless":
            print("headless: isolated Chrome copy of your profile. Your daily Chrome is left alone.", flush=True)
        if args.all:
            print(
                "collect: --all runs an in-page scroller and polls every few seconds "
                "(not one Apple Event per tweet). Stops if X shows a rate-limit wall.",
                file=sys.stderr,
                flush=True,
            )
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
            headless=args.headless,
            all_bookmarks=args.all,
            stop_at_existing=args.stop_at_existing,
            known_streak=getattr(args, "stop_after_known", 8),
        )
        if result.login_required:
            print("X login required. Run `uv run tweetkb login`, finish login, then rerun collect.")
            return 2
        if result.needs_bookmarks_tab:
            if result.debug_targets_empty:
                print("Normal Chrome is open, but Browser-Harness/CDP sees zero tabs. "
                      "Restart normal Chrome with remote debugging enabled:\n"
                      "uv run tweetkb chrome-debug\n"
                      "Then open https://x.com/i/history and rerun:\n"
                      "uv run tweetkb collect --normal-chrome --existing-tab")
            else:
                suffix = " --normal-chrome" if args.normal_chrome else ""
                print(f"Open https://x.com/i/history in Chrome, then rerun with `uv run tweetkb collect{suffix} --existing-tab`.")
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

    if args.cmd == "search":
        return _cmd_search(args, store)

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
    print(message, file=sys.stderr, flush=True)


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


def _cmd_unbookmark(args, store) -> int:
    from .unbookmark import list_unbookmark_candidates, mark_unbookmarked, unbookmark_on_x

    query = (getattr(args, "search", "") or "").strip()
    ids = list(getattr(args, "ids", None) or [])
    if query:
        candidates = list_unbookmark_candidates(store, query, limit=getattr(args, "limit", 50) or 50)
        if getattr(args, "as_json", False):
            print(
                json.dumps(
                    {
                        "candidates": [
                            {
                                "status_id": item.status_id,
                                "status_url": item.status_url,
                                "author_handle": item.author_handle,
                                "snippet": item.snippet,
                            }
                            for item in candidates
                        ]
                    }
                )
            )
        else:
            for item in candidates:
                handle = f"@{item.author_handle}" if item.author_handle else "-"
                print(f"{item.status_id}  {handle}")
                print(item.snippet)
                if item.status_url:
                    print(item.status_url)
                print()
            if candidates:
                joined = " ".join(item.status_id for item in candidates)
                print(f"unbookmark with: tweetkb unbookmark --ids {joined} --yes", file=sys.stderr)
        return 0
    if not ids:
        print("search or --ids is required\nTry: tweetkb unbookmark --search rust", file=sys.stderr)
        return 2
    if not getattr(args, "yes", False):
        joined = " ".join(ids)
        print("Refusing to remove X bookmarks without --yes.", file=sys.stderr)
        print(f"Did you mean: tweetkb unbookmark --ids {joined} --yes", file=sys.stderr)
        print("Local copies stay in TweetKB.", file=sys.stderr)
        return 2
    for status_id in ids:
        result = unbookmark_on_x(status_id, browser_app=getattr(args, "browser_app", None) or "Google Chrome")
        if not result.get("ok"):
            print(f"could not unbookmark {status_id}: {result.get('reason', 'unknown')}", file=sys.stderr)
            print("Local row was not marked. Open https://x.com/i/history and retry.", file=sys.stderr)
            return 1
        mark_unbookmarked(store, status_id)
        print(f"unbookmarked {status_id}")
    return 0


def _cmd_tui(store) -> int:
    try:
        from .tui_app import run_tui
    except ImportError:
        print("TUI needs textual. Try: uv sync --extra tui", file=sys.stderr)
        return 2
    return run_tui(store)


def _cmd_related(args, store) -> int:
    from .relations import format_related, parse_kinds, related_bookmarks

    try:
        kinds = parse_kinds(getattr(args, "kinds", None))
        hits = related_bookmarks(
            store,
            args.status_id,
            kinds=kinds,
            limit=getattr(args, "limit", 20) or 20,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    center = store.conn.execute(
        """
        SELECT b.status_id, b.author_handle,
               IFNULL((SELECT c.category_slug FROM classifications c WHERE c.bookmark_id = b.id AND c.is_primary = 1 LIMIT 1), '') AS category
        FROM bookmarks b WHERE b.status_id = ?
        """,
        (args.status_id,),
    ).fetchone()
    if getattr(args, "as_json", False):
        print(
            json.dumps(
                {
                    "center": args.status_id,
                    "author_handle": (center["author_handle"] if center else "") or "",
                    "category": (center["category"] if center else "") or "",
                    "edges": [
                        {
                            "to": hit.status_id,
                            "kind": hit.kind,
                            "via": hit.via,
                            "author_handle": hit.author_handle,
                            "status_url": hit.status_url,
                            "tweet_text": hit.tweet_text,
                            "category": hit.category,
                        }
                        for hit in hits
                    ],
                }
            )
        )
        return 0
    print(format_related(dict(center) if center else {"status_id": args.status_id}, hits))
    return 0


def _cmd_map(args, store) -> int:
    from .relations import author_map, format_author_map

    try:
        payload = author_map(store, getattr(args, "from_handle", "") or "", limit=getattr(args, "limit", 20) or 20)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if getattr(args, "as_json", False):
        print(json.dumps(payload, indent=2))
        return 0
    print(format_author_map(payload))
    return 0


def _cmd_atlas(args, store) -> int:
    from .relations import write_atlas

    out = Path(getattr(args, "out", None) or "exports/atlas.html")
    path = write_atlas(store, out, limit=getattr(args, "limit", 20) or 20)
    print(str(path))
    if getattr(args, "open_atlas", False):
        return _open_urls([str(path.resolve())])
    return 0


def _cmd_search(args, store) -> int:
    from .normalize import display_tweet_text
    from .search import search_bookmarks

    query = " ".join(args.query) if isinstance(args.query, list) else (args.query or "")
    try:
        hits = search_bookmarks(
            store,
            query,
            limit=getattr(args, "limit", 50) or 50,
            from_handle=getattr(args, "from_handle", None),
            category=getattr(args, "category", None),
            domain=getattr(args, "domain", None),
            sort=getattr(args, "sort", "rank") or "rank",
            saved_after=getattr(args, "saved_after", None),
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    as_json = bool(getattr(args, "as_json", False))
    if as_json:
        print(
            json.dumps(
                {
                    "hits": [
                        {
                            "status_id": hit.status_id,
                            "status_url": hit.status_url,
                            "author_handle": hit.author_handle,
                            "tweet_text": hit.tweet_text,
                            "snippet": hit.snippet,
                            "rank": hit.rank,
                            "category": hit.category,
                            "outbound_links": list(hit.outbound_links),
                            "captured_at": hit.captured_at,
                            "created_at": hit.created_at,
                        }
                        for hit in hits
                    ]
                }
            )
        )
    elif not hits:
        print("no matches", file=sys.stderr)
    else:
        for hit in hits:
            handle = f"@{hit.author_handle}" if hit.author_handle else "-"
            category = hit.category or "-"
            text = display_tweet_text(hit.tweet_text or hit.snippet or "")
            print(f"{hit.status_id}  {handle}  {category}")
            print(text[:240])
            if hit.status_url:
                print(hit.status_url)
            for url in hit.outbound_links:
                print(url)
            print()
    open_count = getattr(args, "open_count", None)
    if open_count:
        return _open_urls([hit.status_url for hit in hits if hit.status_url][: int(open_count)])
    return 0


def _open_urls(urls: list[str]) -> int:
    import shutil
    import subprocess

    if not urls:
        print("no urls to open", file=sys.stderr)
        return 0
    opener = shutil.which("open") or shutil.which("xdg-open")
    if not opener:
        print("no system opener found; install macOS open or xdg-open", file=sys.stderr)
        print("Try: tweetkb search QUERY --json", file=sys.stderr)
        return 1
    for url in urls:
        subprocess.run([opener, url], check=False)
    print(f"opened={len(urls)}", file=sys.stderr)
    return 0


def _rewrite_argv(argv: list[str]) -> list[str] | None:
    from .agent import ALIASES, KNOWN_COMMANDS, closest_command

    flags = []
    rest = list(argv)
    while rest and rest[0].startswith("-"):
        flag = rest.pop(0)
        flags.append(flag)
        if flag in {"--db", "--browser-app", "--browser-profile", "--debug-port"} and rest:
            flags.append(rest.pop(0))
    if not rest:
        return argv
    head = rest[0]
    if head in ALIASES:
        return flags + [ALIASES[head], *rest[1:]]
    if head in KNOWN_COMMANDS or head.startswith("-"):
        return argv
    suggestion = closest_command(head)
    print(f"unknown command {head!r}", file=sys.stderr)
    if suggestion:
        extra = " ".join(rest[1:])
        print(f"Did you mean: tweetkb {suggestion}{(' ' + extra) if extra else ''}", file=sys.stderr)
    else:
        print("Try: tweetkb search QUERY --json", file=sys.stderr)
        print("     tweetkb capabilities --json", file=sys.stderr)
    return None


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
