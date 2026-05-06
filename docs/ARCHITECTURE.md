# Architecture

## Overview

tweetkb is a local-first X/Twitter bookmark knowledge base. It collects bookmarks via browser automation, stores them in SQLite, analyzes them with deterministic local algorithms, builds a knowledge graph, proposes project ideas, and exports to multiple knowledge tools.

## Design Principles

1. **Local-first**: All data stays on disk. No cloud dependencies for core functionality.
2. **SQLite as source of truth**: Structured data in SQLite. Exports are adapters, not replacements.
3. **Deterministic analysis**: No LLM required. Optional LLM disabled by default.
4. **Backward compatible CLI**: Existing commands still work.
5. **No hardcoded paths**: All paths resolved from cwd, env, or config.

## System Diagram

```
Collectors (Browser-Harness, Apple Events)
         |
         v
  SQLite DB (source of truth)
    bookmarks | authors | links | entities | categories
    classifications | clusters | projects | reviews | exports
         |
         v
  Analyzer Pipeline
    normalize -> classify -> entities -> embed -> cluster -> projects -> review-flags
         |
         v
  Export Adapters
    Obsidian | Logseq | Generic Markdown | JSONL | CSV
         |
         v
  Local UI (review server) | Vault (Obsidian/Logseq)
```

## Module Map

```
src/tweetkb/
  __init__.py          Package init, version
  cli.py               CLI entrypoint, argument parsing
  config.py            Config file loading, env var resolution
  db.py                SQLite Store, connection management
  migrations.py        Schema migration framework
  models.py            Dataclasses for all entities
  collector.py         Browser-Harness and Apple Events collectors
  analyzer.py          Pipeline orchestrator
  classifier.py         Multi-label taxonomy classifier
  entities.py          Entity extraction from text/links/domains
  embeddings.py        Embedding provider abstraction
  graph.py             Graph builder, edge creation
  clusters.py          Cluster generation from bookmarks
  projects.py          Project idea mining from clusters
  exporter.py          Legacy single-exporter (deprecated)
  exporters/
    __init__.py        Adapter registry
    obsidian.py        Obsidian Markdown adapter
    logseq.py          Logseq Markdown adapter
    markdown.py        Generic Markdown adapter
    jsonl.py           JSON Lines adapter
    csv.py             CSV adapter
  server.py            Review UI HTTP server
  review.py            Review state machine, actions
  embeddings.py        Local and optional provider embedding helpers
  util.py              Shared utilities
  compress.py          TweetZip compression (Python reference impl)
```

## Data Flow

### Collection
1. Browser-Harness scrolls x.com/i/bookmarks, extracts tweet data
2. Collector calls `store.upsert_bookmark()` for each tweet
3. Bookmark deduplicated by `status_id`
4. `content_hash` skips re-analysis of unchanged bookmarks
5. Collection run logged to `collection_runs`

### Analysis
1. `tweetkb analyze` runs pipeline stages
2. Each stage is idempotent, skips unchanged rows via `content_hash`
3. Classification: multi-label keyword + URL rules
4. Entities: regex + known terms + URL patterns
5. Embeddings: local hash vector (optional Ollama/OpenAI)
6. Clustering: category + entity overlap grouping
7. Projects: heuristic extraction from high-signal clusters

### Export
1. `tweetkb export --adapter <name>` runs selected adapter
2. Adapter reads from SQLite (not from export cache)
3. Each adapter transforms bookmark rows to target format
4. Export runs logged to `export_runs`

## Key Design Decisions

### Why JSON columns for some enrichment?
Rich structured fields (entities, links, tags) stored as JSON in `bookmarks` for simplicity. When these grow large or need querying, they migrate to proper join tables.

### Why FTS5?
Full-text search on tweet text, summary, and author fields via SQLite FTS5 virtual table with triggers keeping it in sync.

### Why varint encoding in TweetZip?
Variable-length integer encoding reduces record headers by 50-80% for typical tweet IDs and counts.

### Why heuristic clustering?
Avoids LLM dependency. Groups bookmarks by category + entity + domain overlap. Configurable threshold.

### Why optional LLM?
Users may want AI classification but shouldn't require API keys. Provider abstraction allows local Ollama or cloud OpenAI as opt-in.

## Performance Characteristics

- **Collection**: ~50-100 bookmarks/minute via browser scroll
- **Classification**: ~1000 bookmarks/second (local heuristic)
- **Export**: ~500 notes/second for Obsidian
- **FTS search**: Sub-100ms for 10K bookmarks
- **TweetZip compress**: ~10K records/second

## Future Considerations

- Move embeddings to a proper vector column (SQLite doesn't support native vectors)
- Add graph export to GraphML for external visualization
- Scaffold Tauri desktop app when backend is stable
- Add RSS/link enricher as alternative collector
