# MiniMax Master Prompt: TwitterOrganizer Full Build

Important MiniMax environment note: you have your own tool suite available under `/Users/Aditya/AI/MiniMax/tools` (also reachable on this Mac as `/Users/aditya/AI/MiniMax/tools`; Windows-style reference: `\Users\Aditya\AI\MiniMax\tools`). Inspect and use those tools before claiming something cannot be done. If a task seems blocked, search the repo and the available AI/MiniMax tools first. Prefer using the provided tools, scripts, and local capabilities over stopping. Do not tell the user you cannot do something until you have inspected the relevant tools folder, local commands, docs, and repository code.

Full autonomous mode instruction: do not get stuck because a tool is missing. If you need a small helper, generator, migration runner, benchmark harness, fixture builder, schema inspector, graph exporter, compression tester, or validation script, build that tool inside the repo and keep going. If a third-party binary is missing, first look for an existing local equivalent, then implement a minimal replacement, then degrade gracefully with a documented fallback. Choose sensible defaults. Keep working through the full framework overnight. Leave a progress log and final report. Your job is not to stop at "I cannot"; your job is to inspect, adapt, build the missing piece when reasonable, and continue until the backend framework is substantially complete.

You are MiniMax operating as a senior full-stack systems engineer. You are working inside the `TwitterOrganizer` repository. Your job is to build the next major version of this project end-to-end: backend, analyzer, knowledge graph, export adapters, review workflows, and the foundation for a desktop app. Work autonomously overnight. Make high-quality production-minded changes with tests, docs, and clean commits if you are allowed to commit. If committing is not allowed by the runner, leave the worktree cleanly organized with a detailed final report.

Do not ask for clarification unless the repo is impossible to inspect. Prefer concrete implementation. Do not hardcode user-specific paths, account names, local home directories, credentials, browser profile paths, vault paths, or private repository URLs. The project must remain useful to any user who clones it.

## Current Project Summary

TwitterOrganizer is a local-first X/Twitter bookmark knowledgebase.

Current capabilities:

- Collects visible X/Twitter bookmarks through Browser-Harness or Apple Events.
- Stores bookmarks in SQLite.
- Dedupe is by tweet status ID.
- Re-running collection is safe.
- Classifies bookmarks into a simple taxonomy.
- Exports Markdown notes for Obsidian.
- Supports export category filters.
- Serves a simple local review UI.

Current tech:

- Python package in `src/tweetkb`.
- CLI entrypoint: `tweetkb`.
- SQLite database at `data/bookmarks.sqlite3` by default.
- Tests under `tests`.
- `uv` for Python environment.

Current command examples:

```bash
uv sync --extra dev
uv run tweetkb init
uv run tweetkb collect --apple-events --all --batch-size 10 --wait 1
uv run tweetkb classify
uv run tweetkb export --vault ./obsidian-vault --exclude-category misc
uv run tweetkb serve
uv run --extra dev pytest
```

## Non-Negotiable Engineering Requirements

1. No user-specific hardcoded paths.
2. No secrets in code, tests, docs, fixtures, or commits.
3. Everything local-first by default.
4. SQLite remains the source of truth.
5. Markdown export remains an adapter, not the source of truth.
6. Obsidian support must not lock the project into Obsidian.
7. Add Logseq/generic Markdown compatibility where practical.
8. Browser collection must never post, like, follow, unfollow, delete, message, or change account settings.
9. All collection actions must be read-only except scrolling/navigation.
10. Re-running import must be idempotent.
11. All substantial features need tests.
12. CLI output must be concise and useful.
13. Public APIs and schemas must be documented.
14. The project should be viable as open source later.
15. Keep the current working commands compatible unless there is a strong reason to change them.
16. Keep the language footprint small. Use at most three implementation languages in this repository.
17. Preferred language set: Python for orchestration and analysis, Zig for native performance modules, and TypeScript only if a real desktop/web UI is added.
18. Do not introduce Rust, Go, Java, Swift, Kotlin, C++, or shell-heavy subsystems unless you remove a planned language or document a compelling reason.
19. Build a custom experimental compression algorithm in Zig or Python, but do not make it the default live SQLite storage path until it is benchmarked and proven safe.
20. Any Zig usage must be purposeful, tested, and optional from the Python CLI when Zig is not installed.

## Autonomous Operating Protocol

Operate like a high-agency overnight build agent.

Do:

- inspect before asking
- search before inventing
- use the MiniMax tools folder before declaring a blocker
- build small missing tools when they unblock the main work
- choose conservative defaults
- keep existing commands working
- run tests repeatedly
- write docs as you go
- leave the repo in a runnable state
- preserve user data
- prefer additive migrations over destructive changes
- log major decisions in `docs/BUILD_LOG.md`
- create `docs/MINIMAX_FINAL_REPORT.md` at the end

Do not:

- stop because a helper script does not exist
- stop because a fixture does not exist
- stop because an optional dependency is missing
- stop because a command needs a small wrapper
- stop because a schema inspector is needed
- stop because a benchmark harness is needed
- stop because an export verifier is needed
- stop because you need synthetic data
- stop because Zig is not installed
- stop because live X/Twitter is unavailable
- ask the user to make product decisions that can be handled with clear defaults

When blocked:

1. Inspect local files and docs.
2. Inspect `/Users/Aditya/AI/MiniMax/tools`.
3. Search the repo.
4. Build a minimal helper if it is small.
5. Add a fallback path.
6. Mark limitation in `docs/BUILD_LOG.md`.
7. Continue with the next valuable task.

Examples:

- Need synthetic bookmarks? Add `tools/generate_synthetic_bookmarks.py` or a test fixture builder.
- Need schema introspection? Add `tweetkb doctor` or `tools/inspect_schema.py`.
- Need graph validation? Add `tools/validate_graph.py`.
- Need compression corpus? Add `tweetkb compress benchmark --synthetic`.
- Need Zig unavailable? Keep Python engine working and document Zig integration points.
- Need browser unavailable? Skip live collection tests and use DOM fixtures.
- Need LLM unavailable? Use deterministic local analyzer and provider stubs.
- Need Obsidian unavailable? Export Markdown to a folder and validate file structure.

Progress expectation:

- Make meaningful backend progress even if UI is not finished.
- Build vertical slices over isolated stubs.
- Prefer a working simple implementation over an unfinished grand abstraction.
- If time is limited, prioritize migrations, analyzer, entities, export adapters, graph, compression, tests, docs.
- Avoid spending the whole night on visual polish or Tauri setup before the backend is real.

Autonomous final state should include:

- runnable CLI
- migrated DB
- richer analysis
- graph/project data
- export adapters
- compression experiment
- tests
- docs
- final report

## Completion Standard For This Run

Do not stop after implementing one or two isolated pieces. Continue until the whole backend framework is substantially built, hardened, tested, documented, and ready for review.

This means:

- make a complete implementation pass
- run tests
- inspect failures
- fix failures
- run tests again
- inspect code quality
- optimize obvious slow or fragile paths
- add missing tests
- run tests again
- update docs
- run final checks
- write final report

Use multiple passes:

```text
Pass 1: inspect and plan in BUILD_LOG
Pass 2: schema and migrations
Pass 3: analysis pipeline
Pass 4: entities, graph, clusters, projects
Pass 5: export adapters
Pass 6: custom TweetZip compression
Pass 7: review API and UI improvements
Pass 8: tests and fixtures
Pass 9: docs and CI
Pass 10: performance, hardening, cleanup
Pass 11: final verification and report
```

If time is short, finish backend correctness before UI polish.

## Research Requirement

Do targeted research before implementing major subsystems. Do not over-research forever.

Research checklist:

- SQLite migrations and FTS5 usage
- SQLite compaction and `VACUUM`
- SQLite page stats
- Obsidian frontmatter/link conventions
- Logseq Markdown conventions
- JSONL and CSV export conventions
- simple graph clustering approaches
- varint encoding
- dictionary compression
- Zig build/test conventions
- Tauri v2 only if you scaffold desktop

Record useful findings in `docs/BUILD_LOG.md` with links or source names.

Use primary sources when available. If offline, inspect installed docs, tool help, examples, and local packages.

## Hardening Requirements

After initial implementation, harden the code.

Hardening checklist:

- all CLI commands have useful `--help`
- errors are actionable
- no tracebacks for expected user mistakes
- live collection commands are clearly marked
- tests do not need live browser
- tests do not need live X/Twitter
- tests do not need API keys
- no generated DB or vault output in git
- no user-specific paths in tracked files
- no secrets
- migrations are additive and safe
- export overwrite behavior is documented
- compression verifier exists
- corrupt compressed archives fail cleanly
- provider config is optional
- LLM calls are disabled by default
- missing Zig gives clean fallback
- missing Browser-Harness gives clean message
- missing Apple Events permission gives clean message

## Optimization Requirements

Do not prematurely micro-optimize, but do remove obvious inefficiencies.

Optimize:

- repeated DB writes with transactions
- repeated classification of unchanged bookmarks
- repeated entity extraction of unchanged bookmarks
- export loops that rewrite unchanged files unnecessarily if easy
- large JSON loads where streaming is simple
- SQLite indexes for common filters
- TweetZip encode/decode on synthetic corpora

Add benchmark commands where useful:

```bash
uv run tweetkb benchmark
uv run tweetkb benchmark --stage export
uv run tweetkb benchmark --stage compress
uv run tweetkb compress benchmark
```

Benchmarks should be informative, not perfect.

## Test Matrix

Run a real test matrix before final report:

```bash
uv run --extra dev pytest
uv run python -m compileall src tests
uv run tweetkb init --db /tmp/tweetkb-test.sqlite3
uv run tweetkb stats --db /tmp/tweetkb-test.sqlite3
uv run tweetkb export --vault /tmp/tweetkb-vault --exclude-category misc
uv run tweetkb compress benchmark
uv run tweetkb compress export --out /tmp/bookmarks.twz
uv run tweetkb compress verify /tmp/bookmarks.twz
uv run tweetkb compress decompress /tmp/bookmarks.twz --out /tmp/bookmarks.jsonl
```

If exact commands differ after implementation, run equivalent commands and document the difference.

Do not fake test results. If something cannot run, explain exactly why and what was run instead.

## Git And Commit Guardrails

If allowed to commit:

- keep commits logical
- do not commit local DB files
- do not commit exported vault output
- do not commit secrets
- do not rewrite history unless instructed
- run tests before final commit
- use conventional commit messages

Suggested commit flow:

```text
docs: record architecture and build plan
feat: add migrations and config
feat: add analyzer pipeline
feat: add entity graph and projects
feat: add export adapters
feat: add tweetzip compression
feat: improve review api
test: expand backend coverage
ci: add automated checks
docs: finalize operating guide
```

If not allowed to commit, leave changes organized and include a commit plan.

## Guardrails Against Scope Collapse

Do not spend the whole run on:

- Tauri shell
- CSS polish
- one compression micro-optimization
- one perfect LLM prompt
- live browser debugging
- GitHub metadata
- README polishing only

Always keep moving across the core backend.

Minimum useful overnight outcome:

- migrations
- richer analysis
- entities
- graph/clusters
- projects
- exports
- TweetZip
- tests
- docs

Stretch outcome:

- improved review UI
- Tauri scaffold
- benchmark suite
- CI
- Logseq export
- JSON graph visualization data

## Language Budget And Zig Role

Avoid the common failure mode where a repo becomes a collage of Python, TypeScript, Rust, Go, shell, SQL, YAML, and random generated assets. This project should feel intentionally small.

Language budget:

```text
Python      required  current core engine, CLI, collectors, analysis pipeline
Zig         optional  native graph/index/compaction utilities
TypeScript  optional  only for Tauri/web UI if built
SQL         allowed   embedded migrations and queries, not counted as a general implementation language
Markdown    allowed   docs and exports
YAML/TOML   allowed   config and CI
```

Do not add Rust just because Tauri uses Rust internally unless you actually scaffold Tauri. If Tauri is scaffolded, keep Rust glue minimal and do not move business logic into Rust in this phase. If a Tauri scaffold would force substantial Rust ownership, postpone it and keep building the backend.

Zig should be used if and only if it improves one of these concrete areas:

1. Fast graph export from SQLite query output.
2. Fast similarity/adjacency calculations over compact JSONL/CSV generated by Python.
3. Fast vault/index verification.
4. Optional database maintenance helper that runs `VACUUM`, reports page stats, and verifies file size changes.
5. Optional compressed archive writer for exports using a standard format.

Preferred Zig deliverable:

```text
zig/
  build.zig
  src/
    main.zig
    graph.zig
    compact.zig
  tests/
```

Expose it through Python as optional commands:

```bash
uv run tweetkb graph export --engine python
uv run tweetkb graph export --engine zig
uv run tweetkb compact --engine python
uv run tweetkb compact --engine zig
```

If Zig is not installed:

- commands must fail with a clean message
- Python fallback must continue to work
- tests must not require Zig unless explicitly marked integration

Do not build the primary collector in Zig. Browser automation and Apple Events are better kept in Python.

Do not build the primary analyzer in Zig yet. LLM provider adapters, text heuristics, and schema work are faster and safer in Python.

Do not build a Zig GUI.

## Storage, Compression, And Database Size

The goal is a compact, reliable SQLite database plus an experimental custom compression engine we can benchmark and potentially turn into a differentiator.

Build a custom compression algorithm, preferably in Zig with a Python fallback or Python reference implementation.

Important boundary:

- The live SQLite database must remain normal SQLite by default.
- The custom compressor should be used for backups, graph archives, exported corpora, embedding payload archives, or optional cold-storage blobs.
- Do not store primary tweet text only in a custom opaque format.
- Do not break FTS search, migrations, or direct SQLite inspection.
- The compression format must be documented and versioned.
- The decompressor must be implemented and tested before the compressor is considered complete.

Use this order for live DB compactness:

1. Normalize repeated data into tables:
   - authors
   - links
   - domains
   - entities
   - categories
   - tags
2. Store repeated relationships in join tables.
3. Use content hashes to skip unchanged writes.
4. Avoid storing the same raw text in multiple places.
5. Store derived outputs with `content_hash` so they can be regenerated.
6. Add indexes intentionally, then measure DB size.
7. Use SQLite `VACUUM` after large deletes/exclusions.
8. Use SQLite `PRAGMA page_count`, `page_size`, and `freelist_count` for diagnostics.
9. Use optional compressed backups/exports with standard formats.
10. Only consider row-level compression for large derived blobs, never for core searchable tweet text unless there is also a plain searchable representation.

## Custom Compression Engine

Add a custom compression subsystem named `tweetzip`.

Preferred implementation:

```text
zig/
  build.zig
  src/
    main.zig
    tweetzip.zig
    varint.zig
    bitstream.zig
    dictionary.zig
    checksums.zig
  tests/
    tweetzip_tests.zig
```

Python fallback/reference:

```text
src/tweetkb/compress.py
tests/test_compress.py
```

The custom format should target bookmark corpora, not arbitrary binary files.

Design goals:

- optimized for short text records
- optimized for repeated AI/tool/model vocabulary
- optimized for repeated URLs/domains/authors
- deterministic output
- streaming decode where practical
- fast enough for thousands to hundreds of thousands of bookmarks
- simple enough to audit
- no unsafe data loss
- no external native dependency required

Suggested format name:

```text
TweetZip v1
```

Suggested file extensions:

```text
.tweetzip
.twz
```

TweetZip v1 container:

```text
magic:      "TWZ1"
flags:      u16
record_ct:  varint
dict_len:   varint
dict_blob:  bytes
records:    repeated compressed records
checksum:   u64
```

Record model:

```text
record_id_delta: varint
field_mask:      varint
status_id:       delta or string table reference
author:          dictionary/string table reference
url:             dictionary/string table reference
text:            compressed token stream
metadata:        optional JSON-ish compact block
```

Compression techniques to implement:

1. Static domain dictionary:
   - `https://`
   - `http://`
   - `x.com/`
   - `twitter.com/`
   - `github.com/`
   - `huggingface.co/`
   - `arxiv.org/`
   - `openai.com/`
   - `anthropic.com/`
   - common AI/model/tool tokens

2. Per-archive dynamic dictionary:
   - authors
   - domains
   - repeated URL prefixes
   - repeated entity names
   - repeated category labels
   - top N token n-grams

3. Token stream encoding:
   - split text into words, whitespace, punctuation, URLs, handles, hashtags
   - dictionary references for frequent tokens
   - raw literals for rare tokens
   - varint lengths

4. Delta encoding:
   - numeric status IDs as decimal strings can be delta encoded when sorted
   - timestamps can be delta encoded if present
   - repeated authors/domains use dictionary IDs

5. Optional simple entropy pass:
   - implement a small custom RLE/varint packing pass
   - do not implement a complex arithmetic coder unless the simple format is already complete

6. Checksums:
   - implement deterministic checksum over decompressed records
   - use standard CRC32 or FNV-1a if easier
   - document choice

Required CLI:

```bash
uv run tweetkb compress export --out ./exports/bookmarks.twz
uv run tweetkb compress inspect ./exports/bookmarks.twz
uv run tweetkb compress decompress ./exports/bookmarks.twz --out ./exports/bookmarks.jsonl
uv run tweetkb compress benchmark
uv run tweetkb compress verify ./exports/bookmarks.twz
```

If Zig is available:

```bash
uv run tweetkb compress export --engine zig --out ./exports/bookmarks.twz
uv run tweetkb compress benchmark --engine zig
```

If Zig is not available:

```bash
uv run tweetkb compress export --engine python --out ./exports/bookmarks.twz
```

Compression benchmark must report:

```text
input_jsonl_bytes
tweetzip_bytes
sqlite_bytes
gzip_jsonl_bytes if available through stdlib
compression_ratio_vs_jsonl
compression_ratio_vs_sqlite
encode_ms
decode_ms
records_per_second
roundtrip_ok
```

Test corpus:

- generate synthetic bookmarks
- use current DB if present but do not require it
- include repeated AI/model/tool terms
- include repeated URLs/domains
- include Unicode text
- include empty fields
- include long tweets
- include duplicate authors

Required tests:

- roundtrip single record
- roundtrip many records
- Unicode roundtrip
- URL dictionary roundtrip
- corrupted magic rejects
- corrupted checksum rejects
- benchmark command runs on synthetic data
- Python and Zig outputs must decode to the same logical records if both engines exist

Python API:

```python
from tweetkb.compress import encode_records, decode_records, inspect_archive
```

Zig CLI API:

```bash
zig build run -- compress input.jsonl output.twz
zig build run -- decompress input.twz output.jsonl
zig build test
```

Important:

- This is allowed to be experimental.
- It should be fun and technically interesting.
- It must not endanger user data.
- Always keep the original SQLite DB readable.
- Always provide a verifier.
- Always provide decompression.

Add a `compact` command:

```bash
uv run tweetkb compact
uv run tweetkb compact --dry-run
uv run tweetkb compact --vacuum
uv run tweetkb compact --report
uv run tweetkb compact --backup ./backups/bookmarks.sqlite3.zst
```

Minimum `compact --report` output:

```text
database_path
file_size_bytes
page_size
page_count
freelist_count
bookmark_count
link_count
entity_count
embedding_count
estimated_reclaimable_bytes
```

If adding compressed backups:

- use a standard format such as gzip or zstd
- do not make decompression mandatory for normal app use
- do not compress the live SQLite DB file in place
- write backups atomically
- document restore commands

Optional Zig compact helper:

- may calculate file stats quickly
- may write compressed JSONL graph archives
- may call standard library compression if available
- must not define a novel compression algorithm

If you want to experiment with compression for fun, put it behind:

```bash
uv run tweetkb lab compress
```

and document that it is experimental, not the production storage format.

## Strategic Product Goal

Turn a pile of Twitter bookmarks into an actionable local knowledgebase for builders.

The product should answer:

- What did I bookmark?
- What topics does my bookmark graph show I care about?
- Which bookmarks are about AI agents, models, coding, design, infra, papers, prompts, tools, product ideas, or business?
- Which bookmarks are duplicates, low value, noisy, or incomplete?
- Which bookmarks should become project ideas?
- Which bookmarks connect to each other?
- Which authors or domains repeatedly appear?
- Which tools, papers, repos, models, libraries, prompts, and workflows should I investigate?
- What can be exported to Obsidian, Logseq, or generic Markdown?
- What should stay in SQLite but not pollute the graph?
- What project candidates emerge from the bookmarks?
- What research briefs can be generated from a cluster?

## Target Architecture

Use this architecture unless repo constraints prove it wrong:

```text
Collectors
  X browser collectors
  future archive/API importers
  future RSS/link enrichment importers

SQLite source of truth
  bookmarks
  authors
  links
  tags
  classifications
  entities
  embeddings
  clusters
  projects
  reviews
  exports

Analyzer pipeline
  normalize
  enrich
  classify
  entity extract
  link extract
  embed
  cluster
  score
  project mine
  export

Interfaces
  CLI
  local HTTP review API
  future Tauri desktop app

Export adapters
  Obsidian Markdown
  Logseq Markdown
  generic Markdown
  JSONL
  CSV
```

Do not jump straight into Tauri unless the backend and API are solid. Build the core engine first so any UI can use it.

## Recommended Implementation Order

1. Audit repo.
2. Improve schema with migrations.
3. Add analyzer pipeline abstraction.
4. Add rich classification and entity extraction.
5. Add topic graph tables.
6. Add project mining.
7. Add richer export adapters.
8. Add review API endpoints.
9. Add better local UI if time permits.
10. Add tests and docs.

## Research Tasks

Before implementing final design decisions, research enough to avoid obvious mistakes. Use official docs or primary sources where possible.

Research:

- SQLite FTS5 best practices.
- SQLite migrations in small Python apps.
- Obsidian Markdown conventions.
- Obsidian frontmatter conventions.
- Logseq Markdown graph conventions.
- Tauri v2 architecture if adding desktop scaffolding.
- Current Browser-Harness usage if collector changes are needed.
- Local embedding options if adding optional model integrations.
- OpenAI/Anthropic/local LLM provider patterns only if implementing provider abstraction.

Do not add a paid-service dependency as required. If LLM providers are added, they must be optional.

## Existing Files To Inspect

Inspect these first:

- `README.md`
- `pyproject.toml`
- `src/tweetkb/cli.py`
- `src/tweetkb/db.py`
- `src/tweetkb/collector.py`
- `src/tweetkb/classifier.py`
- `src/tweetkb/exporter.py`
- `src/tweetkb/server.py`
- `src/tweetkb/categories.py`
- `tests/`

## Desired Backend Modules

Add or refactor toward this module layout:

```text
src/tweetkb/
  __init__.py
  cli.py
  config.py
  db.py
  migrations.py
  models.py
  collector.py
  analyzer.py
  classifier.py
  entities.py
  embeddings.py
  graph.py
  projects.py
  exporter.py
  exporters/
    __init__.py
    obsidian.py
    logseq.py
    markdown.py
    jsonl.py
    csv.py
  server.py
  review.py
  providers.py
  util.py
```

If full refactor is too large, preserve existing modules and add new modules incrementally. Avoid breaking current CLI commands.

## Schema Requirements

Create a migration system. Do not rely forever on one large `CREATE TABLE IF NOT EXISTS` string.

Implement:

- `schema_migrations(version integer primary key, name text, applied_at text)`
- ordered migration functions or SQL files
- `tweetkb migrate`
- `tweetkb init` should run migrations
- migrations must be idempotent
- tests for fresh DB and existing DB upgrades

Current `bookmarks` table should evolve without losing data.

Recommended schema:

```sql
bookmarks
  id integer primary key
  status_id text unique not null
  status_url text not null
  author_id integer null
  author_name text
  author_handle text
  tweet_text text not null default ''
  raw_text text not null default ''
  created_at text
  captured_at text not null
  updated_at text not null
  content_hash text not null
  collection_source text not null default 'browser'
  collection_run_id text
  is_archived integer not null default 0
  is_deleted integer not null default 0
  is_exportable integer not null default 1
  needs_review integer not null default 1
  review_note text not null default ''
```

```sql
authors
  id integer primary key
  handle text unique
  display_name text
  profile_url text
  first_seen_at text
  last_seen_at text
  bookmark_count integer default 0
```

```sql
links
  id integer primary key
  url text unique not null
  normalized_url text
  domain text
  title text
  description text
  content_type text
  first_seen_at text
  last_seen_at text
```

```sql
bookmark_links
  bookmark_id integer not null
  link_id integer not null
  role text not null default 'mentioned'
  primary key(bookmark_id, link_id)
```

```sql
categories
  id integer primary key
  slug text unique not null
  label text not null
  description text
  export_default integer not null default 1
  review_default integer not null default 0
```

```sql
classifications
  id integer primary key
  bookmark_id integer not null
  category_slug text not null
  confidence real not null
  method text not null
  rationale text
  created_at text not null
```

```sql
bookmark_category
  bookmark_id integer not null
  category_slug text not null
  confidence real not null
  is_primary integer not null default 0
  primary key(bookmark_id, category_slug)
```

```sql
entities
  id integer primary key
  name text not null
  normalized_name text not null
  type text not null
  source text not null
  unique(normalized_name, type)
```

```sql
bookmark_entities
  bookmark_id integer not null
  entity_id integer not null
  salience real not null default 0.5
  evidence text
  primary key(bookmark_id, entity_id)
```

```sql
tags
  id integer primary key
  name text unique not null
```

```sql
bookmark_tags
  bookmark_id integer not null
  tag_id integer not null
  primary key(bookmark_id, tag_id)
```

```sql
embeddings
  id integer primary key
  bookmark_id integer not null
  provider text not null
  model text not null
  dims integer not null
  vector_json text not null
  content_hash text not null
  updated_at text not null
  unique(bookmark_id, provider, model)
```

```sql
clusters
  id integer primary key
  slug text unique not null
  label text not null
  summary text
  method text not null
  created_at text not null
  updated_at text not null
```

```sql
cluster_members
  cluster_id integer not null
  bookmark_id integer not null
  score real not null
  primary key(cluster_id, bookmark_id)
```

```sql
project_ideas
  id integer primary key
  slug text unique not null
  title text not null
  one_liner text not null
  problem text
  audience text
  why_now text
  implementation_notes text
  source_cluster_id integer
  confidence real not null
  status text not null default 'candidate'
  created_at text not null
  updated_at text not null
```

```sql
project_sources
  project_id integer not null
  bookmark_id integer not null
  role text not null default 'evidence'
  primary key(project_id, bookmark_id)
```

```sql
export_profiles
  id integer primary key
  name text unique not null
  adapter text not null
  vault_path text
  include_categories_json text not null default '[]'
  exclude_categories_json text not null default '[]'
  exclude_review integer not null default 0
  include_projects integer not null default 1
  include_clusters integer not null default 1
  created_at text not null
  updated_at text not null
```

```sql
export_runs
  id integer primary key
  profile_id integer
  adapter text not null
  output_path text not null
  exported_count integer not null
  skipped_count integer not null
  created_at text not null
```

```sql
collection_runs
  id text primary key
  source text not null
  started_at text not null
  finished_at text
  status text not null
  seen_count integer not null default 0
  changed_count integer not null default 0
  unchanged_count integer not null default 0
  error text
  metadata_json text not null default '{}'
```

Preserve existing data. If migration is complex, add compatibility views or populate new tables from old columns.

## Analyzer Pipeline

Implement a pipeline that can be run repeatedly:

```bash
uv run tweetkb analyze
uv run tweetkb analyze --changed-only
uv run tweetkb analyze --provider local
uv run tweetkb analyze --provider openai
uv run tweetkb analyze --stage classify
uv run tweetkb analyze --stage entities
uv run tweetkb analyze --stage graph
uv run tweetkb analyze --stage projects
```

Stages:

1. `normalize`
2. `classify`
3. `entities`
4. `summaries`
5. `embeddings`
6. `clusters`
7. `projects`
8. `review-flags`

Each stage must be idempotent.

Each stage must store method metadata.

Each stage must avoid rewriting unchanged outputs unless inputs changed.

Use `content_hash` to skip unchanged rows.

## Classification System

Replace the simple single-category classifier with a multi-label taxonomy.

Required primary categories:

- `ai-agents`
- `coding`
- `models`
- `evals`
- `tools`
- `design`
- `infra`
- `papers`
- `prompts`
- `workflows`
- `product-ideas`
- `business`
- `security`
- `data`
- `robotics`
- `voice-audio`
- `vision`
- `browser-automation`
- `local-first`
- `open-source`
- `misc`

Each bookmark may have:

- one primary category
- zero or more secondary categories
- confidence per category
- classification method
- rationale

Minimum local classifier:

- keyword rules
- URL/domain rules
- repo/paper/model/tool detection
- author/domain priors
- fallback to existing heuristic

Optional LLM classifier:

- provider abstraction
- JSON schema output
- deterministic retry/repair
- disabled by default unless API key exists

Do not require paid API keys.

## Entity Extraction

Extract entities from text, links, and domains.

Entity types:

- `person`
- `company`
- `product`
- `model`
- `paper`
- `repo`
- `framework`
- `library`
- `protocol`
- `dataset`
- `benchmark`
- `concept`
- `domain`
- `language`
- `cloud`
- `database`
- `app`
- `other`

Examples:

- GPT-5.4 -> model
- Claude Code -> product
- Browser-Harness -> framework/tool
- MCP -> protocol
- SWE-bench -> benchmark
- SQLite -> database
- Tauri -> framework
- Logseq -> app
- Obsidian -> app
- Hugging Face -> company/product
- arXiv link -> paper/source
- GitHub URL -> repo

Normalize names:

- lower-case matching key
- strip punctuation
- canonical aliases
- `x.com` and `twitter.com` should normalize sensibly

Alias table should be configurable in code or data.

## Link Enrichment

Implement link extraction and enrichment.

Do not scrape arbitrary URLs aggressively by default.

Minimum:

- parse domains
- identify GitHub repos
- identify arXiv papers
- identify Hugging Face models/datasets/spaces
- identify YouTube links
- identify docs pages
- identify package registries

Optional enrichment command:

```bash
uv run tweetkb enrich-links
uv run tweetkb enrich-links --limit 100
uv run tweetkb enrich-links --domain github.com
```

Enrichment should:

- use timeouts
- respect robots/terms where relevant
- cache results
- never require browser unless needed
- never block core analysis

## Embeddings

Current deterministic local embeddings are fine as a fallback but weak.

Add provider abstraction:

```text
local-hash
local-model
openai
ollama
custom
```

Default must be `local-hash` or no external call.

Provider config:

- env vars
- CLI options
- config file

Commands:

```bash
uv run tweetkb embed
uv run tweetkb embed --provider local-hash
uv run tweetkb embed --provider ollama --model nomic-embed-text
uv run tweetkb embed --changed-only
```

Store provider, model, dims, vector, and source content hash.

Do not recompute unchanged embeddings.

## Clustering

Implement basic clustering without heavy dependencies first.

Minimum:

- category + entity overlap clustering
- domain/repo/model/paper clustering
- simple cosine similarity over local embeddings
- configurable similarity threshold
- cluster labels generated from top terms/entities

Commands:

```bash
uv run tweetkb cluster
uv run tweetkb cluster --threshold 0.45
uv run tweetkb cluster --min-size 3
```

Cluster outputs:

- cluster label
- summary
- member bookmarks
- top entities
- top links
- top authors
- suggested project ideas

## Project Mining

This is a differentiator.

Build `tweetkb projects` that identifies actionable project candidates.

Inputs:

- clusters
- bookmarks
- entities
- categories
- links

Output project idea fields:

- title
- one-liner
- problem
- target user
- why now
- evidence bookmarks
- relevant tools/repos/models
- build path
- MVP scope
- risk
- moat/differentiation
- open-source angle
- commercial angle
- next actions
- confidence

Commands:

```bash
uv run tweetkb projects
uv run tweetkb projects --from-clusters
uv run tweetkb projects --min-evidence 3
uv run tweetkb projects export --vault ./obsidian-vault
```

Implement local heuristic version first.

Optional LLM version:

```bash
uv run tweetkb projects --provider openai
```

Do not require it.

## Review System

Add review states:

- `new`
- `needs-review`
- `approved`
- `excluded`
- `archived`
- `project-candidate`

Current `needs_review` boolean can remain but should map to richer states.

Review actions:

- approve bookmark
- exclude from export
- edit category
- add/remove tags
- add review note
- mark as project seed
- assign to cluster
- hide low-value item

CLI:

```bash
uv run tweetkb review list
uv run tweetkb review list --category misc
uv run tweetkb review approve <status_id>
uv run tweetkb review exclude <status_id>
uv run tweetkb review tag <status_id> ai-agents
```

HTTP API:

- `GET /api/bookmarks`
- `GET /api/bookmarks/:id`
- `PATCH /api/bookmarks/:id`
- `GET /api/categories`
- `GET /api/entities`
- `GET /api/clusters`
- `GET /api/projects`
- `POST /api/export`

Keep API simple JSON.

## Export System

Refactor exporter into adapters.

Adapters:

- Obsidian
- Logseq
- Generic Markdown
- JSONL
- CSV

Export profiles:

```bash
uv run tweetkb export --adapter obsidian --vault ./obsidian-vault
uv run tweetkb export --adapter logseq --vault ./logseq-graph
uv run tweetkb export --adapter markdown --out ./exports/markdown
uv run tweetkb export --adapter jsonl --out ./exports/bookmarks.jsonl
uv run tweetkb export --adapter csv --out ./exports/bookmarks.csv
```

Filters:

- include categories
- exclude categories
- exclude review
- include/exclude low confidence
- include/exclude project notes
- include/exclude cluster notes
- include/exclude raw tweets

Must support:

```bash
--exclude-category misc
--include-category ai-agents,coding,models
--exclude-review
--min-confidence 0.6
```

Obsidian output:

```text
Bookmarks/
Topics/
Entities/
Authors/
Domains/
Clusters/
Projects/
Indexes/
```

Logseq output:

```text
pages/
journals/ optional
```

Generic Markdown output:

```text
bookmarks/
topics/
entities/
projects/
index.md
```

JSONL output:

- one bookmark per line
- include normalized fields
- include categories/entities/links

CSV output:

- flat table useful for spreadsheets

## Obsidian Note Design

Each bookmark note should include:

- YAML frontmatter
- source URL
- author
- category
- tags
- confidence
- review state
- exported timestamp
- summary
- why it matters
- tweet text
- links
- entities
- related bookmarks
- related clusters
- project candidates

YAML example:

```yaml
---
type: tweet-bookmark
status_id: "123"
source: "https://x.com/user/status/123"
author: "user"
categories:
  - ai-agents
  - browser-automation
confidence: 0.86
review_state: approved
exportable: true
---
```

Use Obsidian links:

```md
[[Topics/AI Agents]]
[[Entities/Browser-Harness]]
[[Projects/Local Agent Bookmark Graph]]
```

## Logseq Note Design

Logseq can read Markdown.

Prefer:

```md
- type:: tweet-bookmark
- status-id:: 123
- source:: https://x.com/user/status/123
- author:: [[Authors/user]]
- categories:: [[AI Agents]], [[Browser Automation]]
- summary:: ...
- why-it-matters:: ...
- tweet::
  - Original text here
- links::
  - https://...
- entities::
  - [[Browser-Harness]]
```

Keep output portable.

## Generic Markdown Design

Generic Markdown should avoid app-specific syntax where possible but still include backlinks in plain text.

Use:

- relative links
- standard YAML frontmatter
- simple folders

## Desktop App Direction

Do not fully build Tauri unless backend is stable. If time remains, scaffold only.

Recommended app stack:

- Tauri v2
- Rust backend commands
- TypeScript frontend
- Svelte or React
- SQLite via Rust or call Python sidecar

Preferred MVP path:

1. Keep Python as core engine.
2. Add stable JSON API.
3. Build Tauri as a shell that talks to local API or invokes Python sidecar.
4. Later move performance-sensitive parts to Rust/Zig if needed.

Do not use Electron unless there is a strong reason. Tauri is lighter.

Do not use Zig as the main application layer for v1. Zig can be used later for:

- fast graph algorithms
- binary indexer
- importer/exporter utilities
- embedding vector search

## Local Web UI Requirements

Improve current server UI.

Views:

- Dashboard
- Collection runs
- Bookmarks table
- Bookmark detail
- Review queue
- Categories
- Entities
- Clusters
- Projects
- Export profiles
- Settings

Dashboard cards:

- total bookmarks
- new since last run
- needs review
- excluded
- category distribution
- top entities
- top authors
- top domains
- project candidates

Bookmark table:

- search
- category filter
- review state filter
- exportable filter
- confidence filter
- author filter
- domain filter
- sort by captured date
- sort by category
- sort by confidence

Bookmark detail:

- text
- source link
- author
- categories
- tags
- entities
- links
- summary
- why it matters
- review note
- related bookmarks
- actions

Actions:

- approve
- exclude
- mark project seed
- edit primary category
- add tag
- remove tag
- add note

Use restrained product UI, not marketing UI.

## Configuration

Add config file support.

File:

```text
tweetkb.toml
```

Possible config:

```toml
[database]
path = "data/bookmarks.sqlite3"

[browser]
app = "Google Chrome"
profile = "~/Library/Application Support/Google/Chrome"
debug_port = 9222

[collect]
batch_size = 10
wait = 1.0
stagnant_batches = 10

[analysis]
default_provider = "local"
changed_only = true

[export.obsidian]
vault = "obsidian-vault"
exclude_categories = ["misc"]
exclude_review = false

[export.logseq]
vault = "logseq-graph"
exclude_categories = ["misc"]
```

Config precedence:

1. CLI args
2. env vars
3. `tweetkb.toml`
4. defaults

Implement only if it can be done cleanly with stdlib or minimal dependency.

## CLI Command Target

Final CLI should support:

```bash
tweetkb init
tweetkb migrate
tweetkb collect
tweetkb collect --apple-events --all
tweetkb collect --normal-chrome --existing-tab
tweetkb analyze
tweetkb classify
tweetkb entities
tweetkb embed
tweetkb cluster
tweetkb projects
tweetkb export
tweetkb export --adapter obsidian
tweetkb export --adapter logseq
tweetkb export --adapter jsonl
tweetkb serve
tweetkb stats
tweetkb doctor
tweetkb review list
tweetkb review approve
tweetkb review exclude
```

Add `doctor` command.

Doctor should check:

- Python version
- database path
- database schema version
- bookmark count
- Browser-Harness executable
- macOS Apple Events availability if on macOS
- browser app existence if on macOS
- CDP port status
- export vault path status
- ignored local data warning

## Open Source Readiness

Add:

- `LICENSE` if not present. Use MIT unless project owner specifies otherwise.
- `CONTRIBUTING.md`.
- `SECURITY.md`.
- `.github/workflows/ci.yml`.
- issue templates if time.
- PR template if time.

CI:

```yaml
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - checkout
      - install uv
      - uv run --extra dev pytest
```

Do not publish secrets.

Do not include local DB or vault output in git.

## Privacy And Safety

Document:

- local DB contains bookmark text
- exported vault contains bookmark text
- no credentials stored
- browser automation uses logged-in browser session
- user should review X/Twitter terms
- app performs read-only collection
- optional LLM providers may send bookmark text externally if enabled
- external providers are disabled by default

Add `SECURITY.md` with:

- report process placeholder
- data handling
- secret handling
- browser automation warning

## Tests To Add

Add tests for:

- migrations fresh DB
- migrations existing DB
- status ID extraction
- URL normalization
- author upsert
- link normalization
- category filtering
- export profile filtering
- Obsidian export
- Logseq export
- JSONL export
- CSV export
- entity extraction
- classifier multi-label output
- project idea generation
- cluster generation
- idempotent analyze rerun
- unchanged bookmark skip
- full archive collection script generation if practical
- doctor output if practical

Use fixtures.

Do not require live X/Twitter in tests.

Do not require Chrome in tests.

Do not require Browser-Harness in tests.

## Quality Bar

Run:

```bash
uv run --extra dev pytest
uv run python -m compileall src tests
```

If adding lint/type tools:

```bash
uv run ruff check
uv run pyright
```

Only add those dependencies if you configure them and tests pass.

## Performance Requirements

Should handle:

- 1,000 bookmarks easily
- 10,000 bookmarks reasonably
- repeated analysis without recomputing unchanged data
- export in seconds for 1,000 notes

Use indexes:

- bookmark status ID
- author handle
- link domain
- bookmark category
- entity normalized name
- review state
- exportable

Use SQLite pragmas sensibly.

Avoid loading huge data repeatedly when a simple query works.

## User Experience Requirements

User should be able to:

1. Clone repo.
2. Run setup.
3. Collect bookmarks.
4. Analyze.
5. Review.
6. Export.
7. Open vault in Obsidian or Logseq.
8. Re-run later after adding bookmarks.
9. See only new/changed bookmarks processed.
10. Keep noisy categories out of graph.

No command should assume the user is named Aditya.

No command should assume a particular absolute path.

No command should assume GitHub username.

No command should assume Obsidian is installed.

## Detailed Build Tasks

### Task 1: Repo Audit

Inspect current code. Identify risks:

- schema monolith
- category is single string
- Apple Events collector is macOS-specific
- no config file
- simple classifier
- simple exporter
- server is basic
- no migrations
- no CI

Write notes into `docs/ARCHITECTURE.md`.

### Task 2: Architecture Docs

Create:

- `docs/ARCHITECTURE.md`
- `docs/ROADMAP.md`
- `docs/DATA_MODEL.md`
- `docs/EXPORTS.md`
- `docs/PRIVACY.md`

Keep docs precise.

### Task 3: Migrations

Implement migration framework.

Requirements:

- `Store.init()` runs migrations.
- fresh DB creates latest schema.
- old DB upgrades.
- tests cover migration.

Do not destroy existing `data/bookmarks.sqlite3`.

### Task 4: Models

Create dataclasses or typed dicts for:

- Bookmark
- Author
- Link
- Category
- Entity
- Classification
- Cluster
- ProjectIdea
- ExportProfile
- CollectionRun

Avoid overengineering.

### Task 5: Multi-Label Classifier

Implement deterministic classifier first.

Output:

```python
{
  "primary": "ai-agents",
  "categories": [
    {"slug": "ai-agents", "confidence": 0.9, "rationale": "..."},
    {"slug": "browser-automation", "confidence": 0.8, "rationale": "..."}
  ],
  "tags": [...],
  "needs_review": false
}
```

Persist both primary and secondary categories.

### Task 6: Entity Extractor

Implement local entity extraction.

Use:

- regex
- known terms table
- URL patterns
- capitalization heuristics

Persist entities and bookmark-entity edges.

### Task 7: Graph Builder

Build graph tables and graph summaries.

Graph edges:

- bookmark to entity
- bookmark to category
- bookmark to author
- bookmark to domain
- bookmark to cluster
- cluster to project

Graph export:

- JSON graph:

```json
{
  "nodes": [],
  "edges": []
}
```

Command:

```bash
uv run tweetkb graph export --out ./exports/graph.json
```

### Task 8: Clusters

Implement cluster command.

Heuristic:

- group by primary category
- split by top entities/domains
- merge if overlap high
- discard clusters smaller than min size

Persist clusters.

### Task 9: Projects

Implement project idea generator.

Heuristic:

- clusters with product/tools/agents/coding/business categories become candidates
- require minimum evidence count
- generate title from top entities/category
- one-liner from cluster summary
- add evidence bookmark links

Persist project ideas.

### Task 10: Export Refactor

Move export code into adapters.

Keep CLI backward compatible:

```bash
tweetkb export --vault ./obsidian-vault
```

New:

```bash
tweetkb export --adapter obsidian --vault ./obsidian-vault
tweetkb export --adapter logseq --vault ./logseq-graph
tweetkb export --adapter jsonl --out ./exports/bookmarks.jsonl
tweetkb export --adapter csv --out ./exports/bookmarks.csv
```

### Task 11: Review API

Expand local server API.

Do not require JS framework unless needed.

If frontend remains vanilla JS, keep it clean.

If adding frontend framework, choose one and document why.

### Task 12: CI

Add GitHub Actions.

Use `uv`.

Do not require browser.

Do not include private data.

### Task 13: Docs

Update README.

Add quick start.

Add architecture docs.

Add privacy docs.

Add export docs.

Add open source notes.

## Acceptance Criteria

The build is successful if:

- Existing commands still work.
- `uv run --extra dev pytest` passes.
- `uv run python -m compileall src tests` passes.
- Database can initialize fresh.
- Existing database can migrate.
- Full collection remains idempotent.
- Analyze command creates classifications/entities/clusters/project ideas.
- Export can omit `misc`.
- Export can target Obsidian and Logseq.
- JSONL export works.
- CSV export works.
- No user-specific absolute paths are committed.
- README explains usage clearly.
- CI exists.
- Local data remains gitignored.

## Suggested Commit Plan

If committing:

```text
docs: add architecture and roadmap
feat: add schema migrations
feat: expand analysis pipeline
feat: add entity and graph extraction
feat: add project idea mining
feat: refactor export adapters
feat: expand review api
test: cover analysis and export flows
ci: add github actions
docs: document privacy and open source setup
```

Keep commits coherent.

## Final Report Required

At the end, report:

- what changed
- files changed
- commands run
- test results
- known limitations
- next recommended work
- whether live collection was touched
- whether database migration is destructive or safe

## Important Warnings

Do not run live X/Twitter collection unless explicitly requested by the user or unless the current task clearly requires it. Tests must not hit X/Twitter.

Do not include the actual local database in commits.

Do not include exported Obsidian vault output in commits.

Do not push to GitHub unless explicitly authorized by the user in this session.

Do not rewrite git history unless explicitly asked.

Do not remove existing functionality while refactoring.

## Build Philosophy

This project should become a local-first intelligence layer over personal bookmarks.

The long-term differentiator is not "save tweets to Markdown." The differentiator is:

- turning messy saved content into an actionable graph
- preserving local ownership
- extracting project opportunities
- supporting multiple open/local knowledge tools
- making review and export controllable
- respecting privacy
- being easy to rerun every week

Build toward that.
