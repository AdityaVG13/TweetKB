TweetKB v0.5.0 makes the interactive bookmark workflow usable end-to-end for logged-in X accounts.

- Added normal Chrome and Apple Events collection paths for users who are already logged in to X in their regular browser.
- Added CDP fallback to Apple Events when Chrome remote debugging is unavailable.
- Added full X Article capture during enrichment.
- Added optional tweet image analysis through OpenAI, Ollama, or metadata-only mode.
- Added `tweetkb media-export` for creating a local image review bundle for manual AI inspection.
- Added `collect --all` stopping when already-saved bookmark history is reached, plus `--no-stop-at-existing` for full rescans.
- Preserved visual bookmark order during collection so enrichment follows the bookmark page order instead of numeric tweet-ID order.
- Added per-stage analysis state so changed-only runs skip unchanged classification, entity extraction, and embedding work.
- Fixed `--stage classify` so it only classifies.
- Reordered the interactive menu to match the intended workflow: collect, enrich, analyze, analyze + export.
- Added enrichment queue preview output so users can see which bookmarks will be opened before the run starts.
- Escaped Apple Events generated scripts correctly when known bookmark IDs are present.
- Updated docs for collection modes, media review bundles, changed-only analysis, and the interactive workflow.

Install or upgrade:

```bash
uv tool install --force git+https://github.com/AdityaVG13/TweetKB.git
uv tool update-shell
```

Open a new terminal, then run:

```bash
tweetkb init
tweetkb
```

Recommended interactive workflow:

```text
3. Collect bookmarks
4. Enrich saved bookmarks
5. Analyze bookmarks
5a. Analyze + export to folder
```

Equivalent CLI flow:

```bash
tweetkb collect --apple-events --all
tweetkb enrich --apple-events --limit 100
tweetkb analyze --stage all
tweetkb analyze-export --stage all --adapter spec --vault ./exports/spec
```

For image-heavy bookmarks without a vision API key:

```bash
tweetkb enrich --apple-events --include-media --vision-provider metadata
tweetkb media-export --out ./exports/media-review
```

For source checkout development:

```bash
git clone https://github.com/AdityaVG13/TweetKB.git TweetKB
cd TweetKB
uv sync --extra dev
uv run tweetkb
```

This release was checked with:

```bash
uv run ruff check .
uv run pytest
uv run python -m compileall src tests tools
uv run tweetkb release-audit
uv build
clamscan -r --infected --bell --exclude-dir='^\.git$' --exclude-dir='^\.venv$' .
clamscan dist/tweetkb-0.5.0*
```

The tracked repository includes only `data/.gitkeep` under `data/`. Public GitHub
source downloads do not include a bookmark database or private X bookmark data.
