# Non-Negotiable Engineering Requirements

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
16. Keep the language footprint small. Use at most three implementation languages.
17. Preferred language set: Python for orchestration and analysis, Zig for native performance modules, and TypeScript only if a real desktop/web UI is added.
18. Do not introduce Rust, Go, Java, Swift, Kotlin, C++, or shell-heavy subsystems unless you remove a planned language or document a compelling reason.
19. Build a custom experimental compression algorithm in Zig or Python, but do not make it the default live SQLite storage path until it is benchmarked and proven safe.
20. Any Zig usage must be purposeful, tested, and optional from the Python CLI when Zig is not installed.

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

## Git And Commit Guardrails

- keep commits logical
- stage every meaningful feature/change as its own commit
- do not make one giant overnight commit
- commit docs separately from implementation unless tightly coupled
- commit tests with the feature they validate when practical
- commit generated helper tools separately
- commit GitHub/CI metadata separately
- do not commit local DB files
- do not commit exported vault output
- do not commit secrets
- do not rewrite history unless instructed
- run tests before final commit
- use conventional commit messages
- push only to `https://github.com/AdityaVG13/TwitterOrganizer.git`

### Commit Granularity Target:
- one commit per subsystem or coherent behavior change
- no commit should mix unrelated backend, UI, docs, and compression work
- avoid commits larger than necessary
- if a commit gets too broad, split it before pushing

### Suggested Commit Flow:
```
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

## Guardrails Against Scope Collapse

Do not spend the whole run on:
- Tauri shell
- CSS polish
- one compression micro-optimization
- one perfect LLM prompt
- live browser debugging
- GitHub metadata
- README polishing only

### Minimum Useful Overnight Outcome:
- migrations
- richer analysis
- entities
- graph/clusters
- projects
- exports
- TweetZip
- tests
- docs

### Stretch Outcome:
- improved review UI
- Tauri scaffold
- benchmark suite
- CI
- Logseq export
- JSON graph visualization data
