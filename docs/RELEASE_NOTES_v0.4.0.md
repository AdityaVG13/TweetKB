TweetKB v0.4.0 adds richer X conversation analysis and an interactive analysis spec export.

- Added question-aware thread/reply enrichment for bookmarked X posts.
- Added `--include-conversation auto|always|never` to `tweetkb enrich`.
- Added `tweetkb analyze-export` for running analysis and export in one command.
- Added terminal menu option `4a. Analyze + export to folder`.
- Added `spec` export, a local interactive `index.html` with search, filters, expandable analysis sections, captured context, links, entities, tags, and visible media metadata.
- Persisted collected links into the local database so exports can show the links used by analysis.
- Captured visible image URL/alt metadata during enrichment when X exposes it.
- Documented how analysis documents are built.

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

Interactive spec export:

```bash
tweetkb analyze-export --stage all --adapter spec --vault ./exports/spec
open ./exports/spec/index.html
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
clamscan dist/tweetkb-0.4.0*
```

The tracked repository includes only `data/.gitkeep` under `data/`. Public GitHub
source downloads do not include a bookmark database or private X bookmark data.

Note: TweetKB records visible image URLs/alt text when available, but v0.4.0 does
not download images, OCR them, or run pixel-level image understanding.
