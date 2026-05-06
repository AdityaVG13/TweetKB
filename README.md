# TweetKB

Turn saved X/Twitter bookmarks into a private, local knowledge base.

TweetKB collects bookmarks from your logged-in browser, stores them in SQLite,
classifies and enriches them locally, and exports clean notes for Obsidian,
Logseq, Markdown, JSONL, or CSV. It is built for people who save useful posts
and then want search, review, clustering, project ideas, and portable exports
without handing their bookmark archive to another service.

## Why TweetKB

- Local-first SQLite database
- Read-only browser collection
- Deterministic local classification by default
- Optional enrichment for long-form posts and linked pages
- Exports to Obsidian, Logseq, Markdown, JSONL, and CSV
- Full-text search and a local review UI
- Release audit to catch private paths, runtime data, and accidental secrets

## Privacy Model

- No bookmark database is shipped in this repository.
- No exported vault is shipped in this repository.
- No browser profile, cookie store, API key, or `.env` file is tracked.
- Runtime data stays under `data/` by default and is ignored by git.
- Cloud LLM providers are disabled unless explicitly enabled.
- Browser collection scrolls and reads visible bookmark content. It does not
  post, like, follow, delete, message, or change account settings.

## Requirements

- Python 3.11 or newer
- `uv`
- Chrome or Chromium for bookmark collection
- `browser-harness` on `PATH` for Browser-Harness collection

Install `uv`:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Official `uv` installation options: <https://docs.astral.sh/uv/getting-started/installation/>

## Quickstart

```bash
git clone https://github.com/AdityaVG13/TweetKB.git TweetKB
cd TweetKB
uv sync --extra dev
uv run tweetkb init
uv run tweetkb --help
```

Run the guided terminal menu:

```bash
uv run tweetkb
```

The menu covers collection, analysis, selected category runs, export, review,
stats, clustering, project ideas, compression, the review server, doctor, and
release audit. Every menu action runs the same underlying `tweetkb ...` command
shown on screen.

Optional local config:

```bash
cp tweetkb.example.toml tweetkb.toml
```

`tweetkb.toml` is ignored because it may contain private paths.

## Collect Bookmarks

Open a Browser-Harness managed Chrome session and log in if needed:

```bash
uv run tweetkb login
```

Then collect a bounded sample:

```bash
uv run tweetkb collect --limit 100 --batch-size 20
```

Use your normal Chrome profile only when you understand the privacy tradeoff:

```bash
uv run tweetkb chrome-debug
uv run tweetkb collect --normal-chrome --existing-tab --limit 100
```

macOS Apple Events fallback:

```bash
uv run tweetkb collect --apple-events --all --batch-size 10 --wait 1
```

Chrome must allow JavaScript from Apple Events for that mode.

## Analyze And Export

```bash
uv run tweetkb analyze --stage all
uv run tweetkb export --adapter obsidian --vault ./obsidian-vault
uv run tweetkb serve
```

Open the local review UI at `http://127.0.0.1:8765`.

Analyze only a selected slice:

```bash
uv run tweetkb analyze --stage all --limit 100
uv run tweetkb analyze --stage entities --include-category ai-agents,coding
uv run tweetkb analyze --stage embed --exclude-category misc --needs-review
```

Category filters use existing classifications. A typical workflow is to run
`uv run tweetkb analyze --stage classify` once, then rerun heavier stages such
as `entities` or `embed` for selected categories.

Useful export filters:

```bash
uv run tweetkb export --adapter markdown --vault ./exports/markdown --exclude-category misc
uv run tweetkb export --adapter jsonl --vault ./exports/jsonl --exclude-review
uv run tweetkb export --adapter csv --vault ./exports/csv --include-category ai-agents,coding,models,tools
```

## Enrich Saved Bookmarks

`enrich` opens saved status URLs in logged-in Chrome and captures long-form
status/article text. It can also capture linked pages when asked.

```bash
uv run tweetkb enrich --apple-events --limit 100 --wait 4 --include-links --max-links 3
uv run tweetkb analyze --stage all
```

## Review

```bash
uv run tweetkb review list --limit 50
uv run tweetkb review approve 1234567890123456789
uv run tweetkb review exclude 1234567890123456789
uv run tweetkb review tag 1234567890123456789 research
uv run tweetkb review junk --limit 25
```

## Compression

TweetZip is an experimental local archive format for bookmark corpora.

```bash
uv run tweetkb compress export --out ./exports/bookmarks.twz
uv run tweetkb compress verify ./exports/bookmarks.twz
uv run tweetkb compress inspect ./exports/bookmarks.twz
```

## For AI Coding Agents

Use these instructions when an AI agent is asked to download, install, or verify
TweetKB.

```text
You are installing TweetKB from source.

Rules:
- Do not ask for X/Twitter credentials.
- Do not inspect or upload browser cookies, browser profiles, `.env`, `data/`,
  `exports/`, or vault folders.
- Do not run `collect`, `enrich`, `chrome-debug`, or `--normal-chrome` unless
  the user explicitly asks you to operate their browser.
- Use synthetic data for tests.

Install and verify:
1. Ensure `uv` exists. If missing, install it from the official Astral docs.
2. Run: git clone https://github.com/AdityaVG13/TweetKB.git TweetKB
3. Run: cd TweetKB
4. Run: uv sync --extra dev
5. Run: uv run tweetkb --db /tmp/tweetkb-smoke.sqlite3 init
6. Run: uv run tweetkb --help
7. Run: uv run pytest
8. Run: uv run ruff check .
9. Run: uv run tweetkb release-audit

Success means the CLI works, tests pass, lint passes, and release audit passes.
```

Shell-only version:

```bash
git clone https://github.com/AdityaVG13/TweetKB.git TweetKB
cd TweetKB
uv sync --extra dev
uv run tweetkb --db /tmp/tweetkb-smoke.sqlite3 init
uv run tweetkb --help
uv run pytest
uv run ruff check .
uv run tweetkb release-audit
```

## Public Release Audit

Run this before publishing source or building artifacts:

```bash
uv run tweetkb release-audit
```

For a local folder that may contain ignored databases or vault exports:

```bash
uv run tweetkb release-audit --strict-worktree
```

See [docs/RELEASE.md](docs/RELEASE.md) for the complete release checklist.

## Development

```bash
uv sync --extra dev
uv run pytest
uv run ruff check .
uv run python -m compileall src tests tools
uv build
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Data model](docs/DATA_MODEL.md)
- [Exports](docs/EXPORTS.md)
- [Privacy](docs/PRIVACY.md)
- [Release](docs/RELEASE.md)
- [Roadmap](docs/ROADMAP.md)
- [Security](SECURITY.md)
