from __future__ import annotations

import argparse
import json
from pathlib import Path

from .checkpoint import Checkpoint
from .classifier import classify_text, embed_text
from .collector import BrowserHarnessCollector
from .db import DEFAULT_DB, Store
from .exporter import export_obsidian, parse_category_csv
from .server import ReviewServer


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tweetkb")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--browser-app", default=None, help="macOS browser app name for Apple Events, default: Google Chrome.")
    parser.add_argument("--browser-profile", type=Path, default=None, help="Browser profile directory containing DevToolsActivePort.")
    parser.add_argument("--debug-port", type=int, default=None, help="Browser remote debugging port, default: 9222.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init")
    sub.add_parser("chrome-debug", help="Restart normal Chrome with remote debugging and open X bookmarks.")
    login = sub.add_parser("login")
    login.add_argument("--normal-chrome", action="store_true", help="Open X bookmarks in the normal Chrome app.")

    collect = sub.add_parser("collect")
    collect.add_argument("--limit", type=int, default=100)
    collect.add_argument("--batch-size", type=int, default=20)
    collect.add_argument("--wait", type=float, default=1.5)
    collect.add_argument(
        "--existing-tab",
        action="store_true",
        help="Use an already-open x.com/i/bookmarks tab instead of opening a new tab.",
    )
    collect.add_argument(
        "--normal-chrome",
        action="store_true",
        help="Connect through the normal Chrome DevToolsActivePort instead of managed Chrome.",
    )
    collect.add_argument(
        "--apple-events",
        action="store_true",
        help="Collect from the active Chrome tab with Apple Events instead of CDP.",
    )
    collect.add_argument(
        "--all",
        action="store_true",
        help="Ignore --limit and keep scrolling until X stops loading new bookmarks.",
    )

    sub.add_parser("classify")

    export = sub.add_parser("export")
    export.add_argument("--vault", type=Path, required=True)
    export.add_argument("--exclude-category", default="", help="Comma-separated categories to omit, e.g. misc,business.")
    export.add_argument("--include-category", default="", help="Comma-separated categories to export exclusively.")
    export.add_argument("--exclude-review", action="store_true", help="Omit bookmarks still marked needs_review.")

    serve = sub.add_parser("serve")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)

    sub.add_parser("stats")

    args = parser.parse_args(argv)
    store = Store(args.db)
    collector = BrowserHarnessCollector(
        store,
        Checkpoint(),
        browser_app=args.browser_app or "Google Chrome",
        browser_profile=args.browser_profile or Path.home() / "Library/Application Support/Google/Chrome",
        debug_port=args.debug_port or 9222,
    )
    try:
        if args.cmd == "init":
            store.init()
            print(f"initialized {args.db}")
            return 0
        store.init()
        if args.cmd == "chrome-debug":
            collector.start_normal_chrome_debug()
            print("Chrome restarted with remote debugging. Log into X if needed, then run `uv run tweetkb collect --normal-chrome --existing-tab`.")
            return 0
        if args.cmd == "login":
            collector.open_login(normal_chrome=args.normal_chrome)
            return 0
        if args.cmd == "collect":
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
                    print(
                        "Normal Chrome is open, but Browser-Harness/CDP sees zero tabs. "
                        "Restart normal Chrome with remote debugging enabled:\n"
                        "uv run tweetkb chrome-debug\n"
                        "Then open https://x.com/i/bookmarks and rerun:\n"
                        "uv run tweetkb collect --normal-chrome --existing-tab"
                    )
                else:
                    suffix = " --normal-chrome" if args.normal_chrome else ""
                    print(f"Open https://x.com/i/bookmarks in Chrome, then rerun with `uv run tweetkb collect{suffix} --existing-tab`.")
                return 3
            print(
                f"saved={result.saved} changed={result.changed} unchanged={result.unchanged} "
                f"seen={result.seen} batches={result.batches} "
                f"scroll_y={result.scroll_y} page_height={result.page_height} visible_articles={result.visible_articles}"
            )
            return 0
        if args.cmd == "classify":
            rows = store.list_bookmarks()
            for row in rows:
                text = "\n".join([row["tweet_text"] or "", row["raw_text"] or ""])
                links = json.loads(row["links_json"] or "[]")
                result = classify_text(text, links)
                store.update_classification(int(row["id"]), result)
                store.set_embedding(int(row["id"]), embed_text(text))
            print(f"classified={len(rows)}")
            return 0
        if args.cmd == "export":
            count = export_obsidian(
                store,
                args.vault,
                exclude_categories=parse_category_csv(args.exclude_category),
                include_categories=parse_category_csv(args.include_category),
                exclude_review=args.exclude_review,
            )
            print(f"exported={count} vault={args.vault}")
            return 0
        if args.cmd == "serve":
            store.close()
            ReviewServer(args.db).serve(args.host, args.port)
            return 0
        if args.cmd == "stats":
            print(json.dumps(store.stats(), indent=2, sort_keys=True))
            return 0
    finally:
        if args.cmd != "serve":
            store.close()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
