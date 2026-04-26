# CLI Command Target

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

## Doctor Command
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

---

# Configuration

### File: `tweetkb.toml`

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

---

# Tests To Add

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

---

# Quality Bar

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

---

# Performance Requirements

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

---

# Open Source Readiness

Add:
- `LICENSE` if not present. Use MIT unless project owner specifies otherwise.
- `CONTRIBUTING.md`
- `SECURITY.md`
- `.github/workflows/ci.yml`
- issue templates if time
- PR template if time

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

---

# Privacy And Safety

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

---

# Acceptance Criteria

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

---

# User Experience Requirements

User should be able to:
1. Clone repo
2. Run setup
3. Collect bookmarks
4. Analyze
5. Review
6. Export
7. Open vault in Obsidian or Logseq
8. Re-run later after adding bookmarks
9. See only new/changed bookmarks processed
10. Keep noisy categories out of graph

No command should assume the user is named Aditya.
No command should assume a particular absolute path.
No command should assume GitHub username.
No command should assume Obsidian is installed.
