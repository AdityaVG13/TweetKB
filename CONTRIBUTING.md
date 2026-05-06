# Contributing

## Setup

```bash
uv sync --extra dev
uv run tweetkb init --db /tmp/tweetkb-test.sqlite3
```

## Checks

Run these checks before sending changes:

```bash
uv run pytest
uv run ruff check .
uv run python -m compileall src tests tools
uv run tweetkb release-audit
```

## Data Hygiene

- Use synthetic bookmarks in tests.
- Do not commit databases, vault exports, browser profiles, cookies, `.env`, or local config.
- Keep examples user-agnostic. Use `example`, `sample`, or `demo` handles.
- Prefer environment variables over committed config for secrets.

## Commits

Use conventional commits:

```text
feat: add export profile support
fix: handle empty bookmark cards
docs: document release audit
```
