# Differentiators To Attempt

After the core system works, attempt at least three differentiators from this list:

## 1. Project Genesis Engine
- turns clusters into concrete project specs
- writes MVP plans
- identifies source bookmarks as evidence
- ranks by feasibility, novelty, leverage, and personal fit

## 2. Research Brief Generator
- creates cluster briefs
- includes claims, tools, links, entities, authors, and next reading
- outputs Markdown notes for vaults

## 3. Knowledge Graph Export
- exports `graph.json`
- nodes: bookmarks, authors, entities, domains, categories, clusters, projects
- edges: mentions, belongs_to, authored_by, links_to, supports_project, related_to

## 4. TweetZip
- custom compression engine
- benchmark against JSONL and SQLite
- verify roundtrip
- document format

## 5. Intelligent Review Queue
- surfaces low-confidence, misc, duplicate-ish, broken-link, and high-value candidates
- batches them for review
- supports accept/exclude/project-seed actions

## 6. Export Profiles
- named export profiles
- Obsidian profile
- Logseq profile
- generic Markdown profile
- JSONL/CSV profile

## 7. Local API Contract
- stable JSON endpoints
- documented request/response shapes
- ready for future Tauri UI

## 8. Doctor And Benchmark
- `tweetkb doctor`
- `tweetkb benchmark`
- actionable output

## 9. Open-Source Readiness
- CI
- LICENSE
- CONTRIBUTING
- SECURITY
- clear privacy model

## 10. Self-Healing Tooling
- repo-local helpers under `tools/`
- schema inspector
- fixture generator
- graph validator
- commit/push helper

---

# Language Budget And Zig Role

Language budget:
```
Python      required  current core engine, CLI, collectors, analysis pipeline
Zig         optional  native graph/index/compaction utilities
TypeScript  optional  only for Tauri/web UI if built
SQL         allowed   embedded migrations and queries
Markdown    allowed   docs and exports
YAML/TOML   allowed   config and CI
```

Zig should be used if and only if it improves one of these concrete areas:
1. Fast graph export from SQLite query output
2. Fast similarity/adjacency calculations over compact JSONL/CSV
3. Fast vault/index verification
4. Optional database maintenance helper
5. Optional compressed archive writer for exports

### Preferred Zig Deliverable:
```
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

---

# Storage, Compression, And Database Size

Use this order for live DB compactness:
1. Normalize repeated data into tables (authors, links, domains, entities, categories, tags)
2. Store repeated relationships in join tables
3. Use content hashes to skip unchanged writes
4. Avoid storing the same raw text in multiple places
5. Store derived outputs with `content_hash` so they can be regenerated
6. Add indexes intentionally, then measure DB size
7. Use SQLite `VACUUM` after large deletes/exclusions
8. Use SQLite `PRAGMA page_count`, `page_size`, and `freelist_count` for diagnostics
9. Use optional compressed backups/exports with standard formats
10. Only consider row-level compression for large derived blobs

---

# Target Architecture

```
Collectors
  X browser collectors
  future archive/API importers
  future RSS/link enrichment importers

SQLite source of truth
  bookmarks, authors, links, tags, classifications
  entities, embeddings, clusters, projects, reviews, exports

Analyzer pipeline
  normalize → enrich → classify → entity extract → link extract → embed → cluster → score → project mine → export

Interfaces
  CLI
  local HTTP review API
  future Tauri desktop app

Export adapters
  Obsidian Markdown, Logseq Markdown, generic Markdown, JSONL, CSV
```

---

# Desktop App Direction

Do not fully build Tauri unless backend is stable. If time remains, scaffold only.

### Recommended App Stack:
- Tauri v2
- Rust backend commands
- TypeScript frontend
- Svelte or React
- SQLite via Rust or call Python sidecar

### Preferred MVP Path:
1. Keep Python as core engine
2. Add stable JSON API
3. Build Tauri as shell that talks to local API or invokes Python sidecar
4. Later move performance-sensitive parts to Rust/Zig if needed

Do not use Electron unless there is a strong reason. Tauri is lighter.
