# Roadmap

## v0.2 - Foundation

### Done
- Schema migration framework
- Multi-label classification
- Entity extraction
- Analyzer pipeline
- Graph tables
- Cluster generation
- Project idea mining
- Export adapters (Obsidian, Logseq, JSONL, CSV)
- Review system expansion
- TweetZip compression experiment
- Doctor/benchmark/compact commands
- Comprehensive tests
- Manual release checklist

### In Progress
- Full backend integration
- Test coverage expansion
- Documentation

## v0.3 - Hardening

- [ ] Deterministic embeddings vs local-model comparison
- [ ] FTS index rebuild command
- [ ] DB vacuum scheduling
- [ ] Incremental export (skip unchanged files)
- [ ] Export diff preview
- [ ] Review queue batching
- [ ] Cluster merge/split commands
- [ ] Project idea refinement UI

## v0.4 - Intelligence

- [ ] LLM classification with JSON schema output
- [ ] LLM project brief generator
- [ ] Entity alias table UI
- [ ] Cross-bookmark entity co-occurrence graph
- [ ] "Related bookmarks" via embedding similarity
- [ ] Anomaly detection (outlier bookmarks)
- [ ] Reading time estimates
- [ ] Duplicate detection improvements

## v0.5 - Connectivity

- [ ] RSS/Atom feed importer
- [ ] Link preview enrichment (title, description, og:image)
- [ ] arXiv paper metadata fetch
- [ ] GitHub repo metadata (stars, language, readme)
- [ ] Hacker News / Lobsters mention detection
- [ ] "Who else bookmarked this" via author analysis

## v0.6 - Desktop

- [ ] Tauri v2 scaffold
- [ ] System tray with collection status
- [ ] Native notifications for collection complete
- [ ] Background collection scheduling
- [ ] Desktop UI: dashboard, review queue, graph view
- [ ] Spotlight/Alfred integration for search

## v1.0 - Personal Intelligence Engine

- [ ] Local embedding model (no external API for embeddings)
- [ ] Semantic search over bookmarks
- [ ] Project tracker (status, progress, links to evidence)
- [ ] "Weekly digest" generated Markdown report
- [ ] Vault sync (Obsidian vault backup/versioning)
- [ ] Import from Pocket, Instapaper, Pinboard
- [ ] Multi-vault support (different export configs for different contexts)

## Open Source Milestones

- [ ] Cross-platform verification on Ubuntu/macOS/Windows
- [x] Installable from GitHub with `uv tool install`
- [ ] pip installable (`pip install tweetkb`)
- [ ] Cross-platform browser automation (Chrome/Firefox/Safari)
- [x] Contributor guide
- [x] Changelog
- [x] Terminal demo
- [ ] Demo video
- [ ] Blog post series

## Backlog

- GraphML export for Gephi/Cytoscape
- SQLite -> DuckDB for analytics queries
- WASM-compiled core for browser-based viewer
- Mobile companion (React Native or Capacitor)
- Multi-user support (separate DBs, shared vault)
- Encryption at rest (SQLCipher)
