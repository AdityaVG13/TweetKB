# TweetKB v0.3.0

TweetKB v0.3.0 is the first public-ready release.

## Highlights

- Renamed the public repo, CLI, and package identity to TweetKB / `tweetkb`.
- Added a no-args terminal menu so `tweetkb` opens an interactive workflow.
- Added progress output for collection, analysis, enrichment, export, and audit flows.
- Added selective analysis filters for category, review state, and limits.
- Added local-first privacy docs and a release audit command.
- Removed committed runtime data, private prompt docs, personal helper scripts, and CI.
- Added public docs for install, release checks, security, contributing, privacy, exports, and architecture.

## Install

```bash
uv tool install git+https://github.com/AdityaVG13/TweetKB.git
uv tool update-shell
```

Open a new terminal, then run:

```bash
tweetkb init
tweetkb
```

For development:

```bash
git clone https://github.com/AdityaVG13/TweetKB.git TweetKB
cd TweetKB
uv sync --extra dev
uv run tweetkb
```

## Verification

This release was checked with:

```bash
uv run pytest
uv run ruff check .
uv run python -m compileall src tests tools
uv run tweetkb release-audit
```

The tracked repository includes only `data/.gitkeep` under `data/`. Public GitHub
source downloads do not include a bookmark database.
