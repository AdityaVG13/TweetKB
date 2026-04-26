# Twitter Bookmark Knowledgebase

Local-first tool for collecting X/Twitter bookmarks, categorizing them, searching them, reviewing them, and exporting Obsidian notes.

## What It Does

- Opens `https://x.com/i/bookmarks` through Browser-Harness.
- Scrolls bookmarks in bounded batches.
- Extracts visible tweet text, author, handle, timestamp, links, quoted/thread text when visible, and status URL.
- Stores everything in SQLite with FTS search, tags, summaries, review state, and deterministic local embeddings.
- Classifies bookmarks into a practical AI/work taxonomy.
- Exports one Markdown note per bookmark plus topic index notes for Obsidian.
- Serves a local review UI for search, filters, tagging, and notes.

Everything is local by default. It does not type credentials. It does not post, like, delete, follow, or send messages.

## Quick Start

```bash
uv sync --extra dev
uv run tweetkb init
uv run tweetkb chrome-debug
uv run tweetkb login
uv run tweetkb login --normal-chrome
```

Log into X in the Browser-Harness managed Chrome window if needed. Then:

```bash
uv run tweetkb collect --limit 100 --batch-size 20
uv run tweetkb classify
uv run tweetkb export --vault ./obsidian-vault
uv run tweetkb serve
```

Open the UI at `http://127.0.0.1:8765`.

## Commands

```bash
uv run tweetkb init
uv run tweetkb login
uv run tweetkb collect --limit 200 --batch-size 25
uv run tweetkb collect --existing-tab --limit 200 --batch-size 25
uv run tweetkb collect --normal-chrome --limit 200 --batch-size 25
uv run tweetkb classify
uv run tweetkb export --vault ./obsidian-vault
uv run tweetkb serve --host 127.0.0.1 --port 8765
uv run tweetkb stats
```

Exclude categories from Obsidian while keeping them in SQLite:

```bash
uv run tweetkb export --vault ./obsidian-vault --exclude-category misc
```

Export only selected categories:

```bash
uv run tweetkb export --vault ./obsidian-vault --include-category ai-agents,coding,models,tools
```

Skip notes that still need review:

```bash
uv run tweetkb export --vault ./obsidian-vault --exclude-review
```

## Files

- SQLite DB: `./data/bookmarks.sqlite3` by default, override with `--db /path/to/bookmarks.sqlite3`.
- Checkpoint: `./data/checkpoint.json`.
- Obsidian export: configured with `--vault`

## Live Collection Notes

The collector uses the installed `browser-harness` executable and the managed Chrome profile at:

```text
~/.browser-harness/chrome-profiles/default
```

If X shows a login wall, finish login manually in that Chrome window and rerun `collect`.

No user-specific filesystem paths are required. Defaults are resolved from the current working directory or the current user's home directory.

macOS browser automation defaults:

- Browser app: `Google Chrome`
- Browser profile: `~/Library/Application Support/Google/Chrome`
- Remote debugging port: `9222`

Override them when needed:

```bash
uv run tweetkb --browser-app "Google Chrome Beta" collect --apple-events --all
uv run tweetkb --browser-profile "$HOME/Library/Application Support/Google/Chrome/Profile 2" collect --normal-chrome --existing-tab
uv run tweetkb --debug-port 9333 chrome-debug
```

If you already have X bookmarks open in Chrome and do not want the collector to open a new tab:

```bash
uv run tweetkb collect --existing-tab --limit 100 --batch-size 20
```

This attaches to an existing `x.com/i/bookmarks` tab and scrolls with page JavaScript. It avoids opening another Chrome tab, but it is not true headless because it is connected to your live browser session.

If you want to use your normal Chrome login instead of the Browser-Harness managed profile:

```bash
uv run tweetkb collect --normal-chrome --limit 100 --batch-size 20
```

Normal Chrome must expose `~/Library/Application Support/Google/Chrome/DevToolsActivePort`. If it does not, open `chrome://inspect/#remote-debugging`, enable remote debugging, and click `Allow`.

If Chrome is already open but was not started with remote debugging, quit Chrome and reopen it with:

```bash
open -na 'Google Chrome' --args --remote-debugging-port=9222 --remote-allow-origins='*'
```

Then open `https://x.com/i/bookmarks` and run:

```bash
uv run tweetkb collect --normal-chrome --existing-tab --limit 100 --batch-size 20
```

Or let the CLI do that restart:

```bash
uv run tweetkb chrome-debug
```

If Chrome refuses CDP on the normal profile, use the Apple Events fallback:

1. In Chrome, enable `View > Developer > Allow JavaScript from Apple Events`.
2. Open `https://x.com/i/bookmarks`.
3. Run:

```bash
uv run tweetkb collect --apple-events --limit 300 --batch-size 20
```

To ingest the full bookmark archive, use:

```bash
uv run tweetkb collect --apple-events --all --batch-size 10 --wait 1
```

This scrolls until X stops producing new unique bookmark IDs. Re-running it is safe: existing tweet IDs are skipped or updated in place.

## Tests

```bash
uv run pytest
```
