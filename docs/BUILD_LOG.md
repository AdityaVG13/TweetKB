# TwitterOrganizer Build Log

## Session: 2026-04-26 — Full Backend Build

## Goals
Build out TwitterOrganizer from a basic bookmark collector into a local-first intelligence engine with: migrations, multi-label analysis, entity graph, clustering, project mining, export adapters, TweetZip compression, review system, and tests.

## Constraints
- Python primary, Zig optional
- SQLite source of truth
- No hardcoded paths
- No secrets
- Backward compatible CLI
- Tests without live X/Twitter

## Progress

### Day 1: Foundation
- [x] Repo audit complete
- [x] Docs: ARCHITECTURE.md, DATA_MODEL.md, EXPORTS.md, PRIVACY.md, ROADMAP.md, BUILD_LOG.md
- [x] Migrations framework (`migrations.py` with version tracking)
- [x] New schema tables (authors, links, entities, clusters, projects, reviews, exports)
- [x] Multi-label classifier (22 categories, confidence scoring, URL-based boosting)
- [x] Entity extractor (type detection: models, frameworks, benchmarks, etc.)
- [x] Analyzer pipeline (classify → entities → embed, staged execution)
- [x] Graph builder (bookmark/author/entity/category nodes and edges)
- [x] Cluster command (category + entity overlap clustering)
- [x] Project mining (heuristic from cluster evidence)
- [x] Export adapters (Obsidian, Logseq, JSONL, CSV, Markdown)
- [x] Review system expansion (state machine with approve/exclude/tag)
- [x] TweetZip compression (v1: varint encoding, dynamic dict, CRC32 checksum)
- [x] CLI: doctor, benchmark, compact, stats, serve
- [x] Tests (36 tests across 14 test files)
- [x] CI (GitHub Actions: pytest + compileall, Python 3.11-3.13 matrix)
- [x] Lint cleanup (32 ruff errors fixed)

## Decisions

### 2026-04-26
- Using `src/tweetkb/migrations.py` for migration framework
- Migration ordering: version 1 = initial extended schema
- TweetZip v1 format: TWZ1 magic, varint headers, dynamic dict, token streams
- Export adapter pattern over single exporter
- Heuristic project mining over LLM (LLM optional, disabled by default)

## Blockers & Resolutions

### TweetZip compression format bugs (resolved)
- **Bug**: Varint decoder infinite loop on `\x00` bytes (continuation bit check never triggered)
- **Bug**: Body/dict boundary ambiguity in decoder (dict_size was entry count not byte size)
- **Bug**: Empty records mismatch between encoder (short format) and decoder (expected full format)
- **Fix**: Rewrote format with explicit body_size and dict_size varints, empty-records flag bit

## Test Results
- `uv run --extra dev pytest`: 36/36 pass
- `uv run --extra dev ruff check src/ tests/`: All checks passed
- `uv run python -m compileall src tests`: pass

## Commands Run
- `2026-04-26 05:44 UTC` [main] feat: add git commit/push tool with conventional commit support
- `2026-04-26 10:30 UTC` [main] feat: fix TweetZip v1 compression with clean varint-based format
- `2026-04-26 10:45 UTC` [main] fix: clean up all lint errors across codebase
