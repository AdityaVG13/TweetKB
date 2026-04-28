from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

SCHEMA_VERSION = 3

# Schema v1: legacy single-table with JSON columns
SCHEMA_V1 = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS bookmarks (
  id INTEGER PRIMARY KEY,
  status_id TEXT UNIQUE,
  status_url TEXT,
  author_name TEXT,
  author_handle TEXT,
  tweet_text TEXT NOT NULL DEFAULT '',
  raw_text TEXT NOT NULL DEFAULT '',
  created_at TEXT,
  captured_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  category TEXT NOT NULL DEFAULT 'misc',
  confidence REAL NOT NULL DEFAULT 0,
  summary TEXT NOT NULL DEFAULT '',
  why_it_matters TEXT NOT NULL DEFAULT '',
  use_cases_json TEXT NOT NULL DEFAULT '[]',
  entities_json TEXT NOT NULL DEFAULT '[]',
  links_json TEXT NOT NULL DEFAULT '[]',
  needs_review INTEGER NOT NULL DEFAULT 1,
  review_note TEXT NOT NULL DEFAULT '',
  content_hash TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS tags (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS bookmark_tags (
  bookmark_id INTEGER NOT NULL REFERENCES bookmarks(id) ON DELETE CASCADE,
  tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
  PRIMARY KEY (bookmark_id, tag_id)
);

CREATE TABLE IF NOT EXISTS embeddings (
  bookmark_id INTEGER PRIMARY KEY REFERENCES bookmarks(id) ON DELETE CASCADE,
  dims INTEGER NOT NULL,
  vector_json TEXT NOT NULL,
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS processing_events (
  id INTEGER PRIMARY KEY,
  bookmark_id INTEGER REFERENCES bookmarks(id) ON DELETE SET NULL,
  event_type TEXT NOT NULL,
  message TEXT NOT NULL DEFAULT '',
  payload_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE VIRTUAL TABLE IF NOT EXISTS bookmarks_fts
USING fts5(tweet_text, summary, why_it_matters, author_name, author_handle, content='bookmarks', content_rowid='id');

CREATE TRIGGER IF NOT EXISTS bookmarks_ai AFTER INSERT ON bookmarks BEGIN
  INSERT INTO bookmarks_fts(rowid, tweet_text, summary, why_it_matters, author_name, author_handle)
  VALUES (new.id, new.tweet_text, new.summary, new.why_it_matters, new.author_name, new.author_handle);
END;

CREATE TRIGGER IF NOT EXISTS bookmarks_ad AFTER DELETE ON bookmarks BEGIN
  INSERT INTO bookmarks_fts(bookmarks_fts, rowid, tweet_text, summary, why_it_matters, author_name, author_handle)
  VALUES('delete', old.id, old.tweet_text, old.summary, old.why_it_matters, old.author_name, old.author_handle);
END;

CREATE TRIGGER IF NOT EXISTS bookmarks_au AFTER UPDATE ON bookmarks BEGIN
  INSERT INTO bookmarks_fts(bookmarks_fts, rowid, tweet_text, summary, why_it_matters, author_name, author_handle)
  VALUES('delete', old.id, old.tweet_text, old.summary, old.why_it_matters, old.author_name, old.author_handle);
  INSERT INTO bookmarks_fts(rowid, tweet_text, summary, why_it_matters, author_name, author_handle)
  VALUES (new.id, new.tweet_text, new.summary, new.why_it_matters, new.author_name, new.author_handle);
END;
"""

# Schema v2: normalized with authors, links, entities, classifications, clusters, projects, reviews, exports
SCHEMA_V2 = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS bookmarks (
  id INTEGER PRIMARY KEY,
  status_id TEXT UNIQUE NOT NULL,
  status_url TEXT NOT NULL,
  author_id INTEGER,
  author_name TEXT,
  author_handle TEXT,
  tweet_text TEXT NOT NULL DEFAULT '',
  raw_text TEXT NOT NULL DEFAULT '',
  created_at TEXT,
  captured_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  content_hash TEXT NOT NULL,
  collection_source TEXT NOT NULL DEFAULT 'browser',
  collection_run_id TEXT,
  is_archived INTEGER NOT NULL DEFAULT 0,
  is_deleted INTEGER NOT NULL DEFAULT 0,
  is_exportable INTEGER NOT NULL DEFAULT 1,
  needs_review INTEGER NOT NULL DEFAULT 1,
  review_note TEXT NOT NULL DEFAULT '',
  review_state TEXT NOT NULL DEFAULT 'new',
  summary TEXT NOT NULL DEFAULT '',
  why_it_matters TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS authors (
  id INTEGER PRIMARY KEY,
  handle TEXT UNIQUE,
  display_name TEXT,
  profile_url TEXT,
  first_seen_at TEXT,
  last_seen_at TEXT,
  bookmark_count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS links (
  id INTEGER PRIMARY KEY,
  url TEXT UNIQUE NOT NULL,
  normalized_url TEXT,
  domain TEXT,
  title TEXT,
  description TEXT,
  content_type TEXT,
  first_seen_at TEXT,
  last_seen_at TEXT
);

CREATE TABLE IF NOT EXISTS bookmark_links (
  bookmark_id INTEGER NOT NULL,
  link_id INTEGER NOT NULL,
  role TEXT NOT NULL DEFAULT 'mentioned',
  PRIMARY KEY (bookmark_id, link_id)
);

CREATE TABLE IF NOT EXISTS categories (
  id INTEGER PRIMARY KEY,
  slug TEXT UNIQUE NOT NULL,
  label TEXT NOT NULL,
  description TEXT,
  export_default INTEGER NOT NULL DEFAULT 1,
  review_default INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS classifications (
  id INTEGER PRIMARY KEY,
  bookmark_id INTEGER NOT NULL,
  category_slug TEXT NOT NULL,
  confidence REAL NOT NULL,
  method TEXT NOT NULL,
  rationale TEXT,
  is_primary INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  UNIQUE(bookmark_id, category_slug)
);

CREATE TABLE IF NOT EXISTS entities (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  normalized_name TEXT NOT NULL,
  type TEXT NOT NULL,
  source TEXT NOT NULL,
  UNIQUE(normalized_name, type)
);

CREATE TABLE IF NOT EXISTS bookmark_entities (
  bookmark_id INTEGER NOT NULL,
  entity_id INTEGER NOT NULL,
  salience REAL NOT NULL DEFAULT 0.5,
  evidence TEXT,
  PRIMARY KEY (bookmark_id, entity_id)
);

CREATE TABLE IF NOT EXISTS tags (
  id INTEGER PRIMARY KEY,
  name TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS bookmark_tags (
  bookmark_id INTEGER NOT NULL,
  tag_id INTEGER NOT NULL,
  PRIMARY KEY (bookmark_id, tag_id)
);

CREATE TABLE IF NOT EXISTS embeddings (
  id INTEGER PRIMARY KEY,
  bookmark_id INTEGER NOT NULL,
  provider TEXT NOT NULL,
  model TEXT NOT NULL,
  dims INTEGER NOT NULL,
  vector_json TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(bookmark_id, provider, model)
);

CREATE TABLE IF NOT EXISTS clusters (
  id INTEGER PRIMARY KEY,
  slug TEXT UNIQUE NOT NULL,
  label TEXT NOT NULL,
  summary TEXT,
  method TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cluster_members (
  cluster_id INTEGER NOT NULL,
  bookmark_id INTEGER NOT NULL,
  score REAL NOT NULL,
  PRIMARY KEY (cluster_id, bookmark_id)
);

CREATE TABLE IF NOT EXISTS project_ideas (
  id INTEGER PRIMARY KEY,
  slug TEXT UNIQUE NOT NULL,
  title TEXT NOT NULL,
  one_liner TEXT NOT NULL,
  problem TEXT,
  audience TEXT,
  why_now TEXT,
  implementation_notes TEXT,
  source_cluster_id INTEGER,
  confidence REAL NOT NULL,
  status TEXT NOT NULL DEFAULT 'candidate',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS project_sources (
  project_id INTEGER NOT NULL,
  bookmark_id INTEGER NOT NULL,
  role TEXT NOT NULL DEFAULT 'evidence',
  PRIMARY KEY (project_id, bookmark_id)
);

CREATE TABLE IF NOT EXISTS export_profiles (
  id INTEGER PRIMARY KEY,
  name TEXT UNIQUE NOT NULL,
  adapter TEXT NOT NULL,
  vault_path TEXT,
  include_categories_json TEXT NOT NULL DEFAULT '[]',
  exclude_categories_json TEXT NOT NULL DEFAULT '[]',
  exclude_review INTEGER NOT NULL DEFAULT 0,
  include_projects INTEGER NOT NULL DEFAULT 1,
  include_clusters INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS export_runs (
  id INTEGER PRIMARY KEY,
  profile_id INTEGER,
  adapter TEXT NOT NULL,
  output_path TEXT NOT NULL,
  exported_count INTEGER NOT NULL,
  skipped_count INTEGER NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS collection_runs (
  id TEXT PRIMARY KEY,
  source TEXT NOT NULL,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  status TEXT NOT NULL,
  seen_count INTEGER NOT NULL DEFAULT 0,
  changed_count INTEGER NOT NULL DEFAULT 0,
  unchanged_count INTEGER NOT NULL DEFAULT 0,
  error TEXT,
  metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS content_enrichments (
  id INTEGER PRIMARY KEY,
  bookmark_id INTEGER NOT NULL,
  source_url TEXT NOT NULL,
  source_type TEXT NOT NULL DEFAULT 'x-status',
  title TEXT NOT NULL DEFAULT '',
  content_text TEXT NOT NULL DEFAULT '',
  content_hash TEXT NOT NULL DEFAULT '',
  captured_at TEXT NOT NULL DEFAULT (datetime('now')),
  metadata_json TEXT NOT NULL DEFAULT '{}',
  UNIQUE(bookmark_id, source_url)
);

CREATE TABLE IF NOT EXISTS processing_events (
  id INTEGER PRIMARY KEY,
  bookmark_id INTEGER,
  event_type TEXT NOT NULL,
  message TEXT NOT NULL DEFAULT '',
  payload_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS schema_migrations (
  version INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  applied_at TEXT NOT NULL
);

-- FTS
CREATE VIRTUAL TABLE IF NOT EXISTS bookmarks_fts
USING fts5(tweet_text, summary, author_name, author_handle, content='bookmarks', content_rowid='id');

-- FTS triggers
CREATE TRIGGER IF NOT EXISTS bookmarks_ai AFTER INSERT ON bookmarks BEGIN
  INSERT INTO bookmarks_fts(rowid, tweet_text, summary, author_name, author_handle)
  VALUES (new.id, new.tweet_text, new.summary, new.author_name, new.author_handle);
END;

CREATE TRIGGER IF NOT EXISTS bookmarks_ad AFTER DELETE ON bookmarks BEGIN
  INSERT INTO bookmarks_fts(bookmarks_fts, rowid, tweet_text, summary, author_name, author_handle)
  VALUES('delete', old.id, old.tweet_text, old.summary, old.author_name, old.author_handle);
END;

CREATE TRIGGER IF NOT EXISTS bookmarks_au AFTER UPDATE ON bookmarks BEGIN
  INSERT INTO bookmarks_fts(bookmarks_fts, rowid, tweet_text, summary, author_name, author_handle)
  VALUES('delete', old.id, old.tweet_text, old.summary, old.author_name, old.author_handle);
  INSERT INTO bookmarks_fts(rowid, tweet_text, summary, author_name, author_handle)
  VALUES (new.id, new.tweet_text, new.summary, new.author_name, new.author_handle);
END;

-- Indexes
CREATE INDEX IF NOT EXISTS idx_bookmarks_status_id ON bookmarks(status_id);
CREATE INDEX IF NOT EXISTS idx_bookmarks_author_handle ON bookmarks(author_handle);
CREATE INDEX IF NOT EXISTS idx_bookmarks_review_state ON bookmarks(review_state);
CREATE INDEX IF NOT EXISTS idx_bookmarks_reviewable ON bookmarks(is_exportable, needs_review, is_deleted);
CREATE INDEX IF NOT EXISTS idx_bookmarks_captured ON bookmarks(captured_at DESC);
CREATE INDEX IF NOT EXISTS idx_classifications_bookmark ON classifications(bookmark_id);
CREATE INDEX IF NOT EXISTS idx_classifications_category ON classifications(category_slug);
CREATE INDEX IF NOT EXISTS idx_entities_normalized ON entities(normalized_name);
CREATE INDEX IF NOT EXISTS idx_bookmark_entities_bookmark ON bookmark_entities(bookmark_id);
CREATE INDEX IF NOT EXISTS idx_bookmark_entities_entity ON bookmark_entities(entity_id);
CREATE INDEX IF NOT EXISTS idx_cluster_members_cluster ON cluster_members(cluster_id);
CREATE INDEX IF NOT EXISTS idx_cluster_members_bookmark ON cluster_members(bookmark_id);
CREATE INDEX IF NOT EXISTS idx_content_enrichments_bookmark ON content_enrichments(bookmark_id);
"""

# Seed data for v2
CATEGORY_SEED = [
    ("ai-agents", "AI Agents", "Autonomous agents, computer use, tool use, agent frameworks", 1, 0),
    ("coding", "Coding", "Programming, repos, debugging, libraries", 1, 0),
    ("evals", "Evals", "Benchmarks, evaluations, leaderboards, quality metrics", 1, 0),
    ("models", "Models", "LLMs, model releases, inference, model comparisons", 1, 0),
    ("tools", "Tools", "Software tools, CLIs, SDKs, libraries, frameworks", 1, 0),
    ("design", "Design", "UI/UX, visual design, design systems", 1, 0),
    ("infra", "Infra", "Infrastructure, deployment, databases, servers", 1, 0),
    ("papers", "Papers", "Research papers, arxiv, academic publications", 1, 0),
    ("prompts", "Prompts", "Prompt engineering, system prompts, instructions", 1, 0),
    ("workflows", "Workflows", "Processes, automation, playbooks, operations", 1, 0),
    ("product-ideas", "Product Ideas", "Startup ideas, product features, MVP concepts", 1, 0),
    ("business", "Business", "GTM, sales, marketing, pricing, revenue", 1, 0),
    ("security", "Security", "Security research, CVEs, exploits", 1, 0),
    ("data", "Data", "Datasets, data engineering, analytics", 1, 0),
    ("robotics", "Robotics", "Robots, hardware, control systems", 1, 0),
    ("voice-audio", "Voice/Audio", "Speech recognition, TTS, audio AI", 1, 0),
    ("vision", "Vision", "Computer vision, image AI, video understanding", 1, 0),
    ("browser-automation", "Browser Automation", "Browser control, web scraping, DOM manipulation", 1, 0),
    ("local-first", "Local-First", "Local-first software, offline-capable, sync", 1, 0),
    ("open-source", "Open Source", "Open source projects, OSS licenses, contributions", 1, 0),
    ("misc", "Misc", "Uncategorized bookmarks", 0, 1),
]

ENTITY_TYPE_ALIASES = [
    # (normalized_name, canonical_type)
    ("gpt", "model"),
    ("claude", "model"),
    ("gemini", "model"),
    ("llama", "model"),
    ("qwen", "model"),
    ("mistral", "model"),
    ("grok", "model"),
    ("browser-harness", "framework"),
    ("mcp", "protocol"),
    ("swe-bench", "benchmark"),
    ("mmlu", "benchmark"),
    ("humaneval", "benchmark"),
    ("sqlite", "database"),
    ("postgres", "database"),
    ("mysql", "database"),
    ("redis", "database"),
    ("tauri", "framework"),
    ("electron", "framework"),
    ("react", "framework"),
    ("svelte", "framework"),
    ("vue", "framework"),
    ("nextjs", "framework"),
    ("vite", "tool"),
    ("webpack", "tool"),
    ("pip", "tool"),
    ("uv", "tool"),
    ("npx", "tool"),
    ("argo", "framework"),
    ("kubernetes", "cloud"),
    ("docker", "tool"),
    ("kubernetes", "cloud"),
    ("tauri", "app"),
    ("obsidian", "app"),
    ("logseq", "app"),
    ("roam", "app"),
    ("notion", "app"),
    ("github", "domain"),
    ("huggingface", "domain"),
    ("arxiv", "domain"),
    ("openai", "company"),
    ("anthropic", "company"),
    ("meta", "company"),
    ("google", "company"),
    ("microsoft", "company"),
    ("apple", "company"),
]


def get_schema_version(conn: sqlite3.Connection) -> int:
    """Return current schema version, 0 if no migrations table."""
    try:
        row = conn.execute("SELECT version FROM schema_migrations ORDER BY version DESC LIMIT 1").fetchone()
        return int(row["version"]) if row else 0
    except sqlite3.OperationalError:
        return 0


def apply_migration(conn: sqlite3.Connection, version: int, name: str) -> None:
    """Record a migration as applied."""
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT OR IGNORE INTO schema_migrations(version, name, applied_at) VALUES (?, ?, ?)",
        (version, name, now),
    )
    conn.commit()


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone() is not None


def _table_columns(conn: sqlite3.Connection, name: str) -> list[str]:
    if not _table_exists(conn, name):
        return []
    return [r["name"] for r in conn.execute(f"PRAGMA table_info({name})").fetchall()]


def _drop_legacy_v1_objects(conn: sqlite3.Connection) -> None:
    """Remove legacy single-table objects after their rows are loaded."""
    conn.executescript(
        """
        DROP TRIGGER IF EXISTS bookmarks_ai;
        DROP TRIGGER IF EXISTS bookmarks_ad;
        DROP TRIGGER IF EXISTS bookmarks_au;
        DROP TABLE IF EXISTS bookmarks_fts;
        DROP TABLE IF EXISTS bookmark_tags;
        DROP TABLE IF EXISTS embeddings;
        DROP TABLE IF EXISTS tags;
        DROP TABLE IF EXISTS processing_events;
        DROP TABLE IF EXISTS bookmarks;
        """
    )


def repair_v2(conn: sqlite3.Connection) -> None:
    """Create missing v2 support tables and repair partially migrated v2 DBs."""
    if _table_exists(conn, "bookmarks") and "category" not in _table_columns(conn, "bookmarks"):
        cols = set(_table_columns(conn, "bookmarks"))
        additions = {
            "author_id": "INTEGER",
            "content_hash": "TEXT NOT NULL DEFAULT ''",
            "collection_source": "TEXT NOT NULL DEFAULT 'browser'",
            "collection_run_id": "TEXT",
            "is_archived": "INTEGER NOT NULL DEFAULT 0",
            "is_deleted": "INTEGER NOT NULL DEFAULT 0",
            "is_exportable": "INTEGER NOT NULL DEFAULT 1",
            "needs_review": "INTEGER NOT NULL DEFAULT 1",
            "review_note": "TEXT NOT NULL DEFAULT ''",
            "review_state": "TEXT NOT NULL DEFAULT 'new'",
            "summary": "TEXT NOT NULL DEFAULT ''",
            "why_it_matters": "TEXT NOT NULL DEFAULT ''",
        }
        for col, ddl in additions.items():
            if col not in cols:
                conn.execute(f"ALTER TABLE bookmarks ADD COLUMN {col} {ddl}")

    conn.executescript(SCHEMA_V2)
    conn.executemany(
        "INSERT OR IGNORE INTO categories(slug, label, description, export_default, review_default) VALUES (?, ?, ?, ?, ?)",
        CATEGORY_SEED,
    )
    conn.commit()


def migrate_to_v2(conn: sqlite3.Connection) -> None:
    """Migrate from v1 schema to v2 normalized schema."""
    # Check if already migrated
    if get_schema_version(conn) >= 2:
        repair_v2(conn)
        return

    # Check if v1 bookmarks table exists
    v1_exists = _table_exists(conn, "bookmarks")
    v1_columns = _table_columns(conn, "bookmarks")
    legacy_v1 = "category" in v1_columns

    now = datetime.now(timezone.utc).isoformat()

    tag_names_by_id: dict[int, str] = {}
    tag_ids_by_bookmark: dict[int, list[int]] = {}

    if v1_exists and legacy_v1:
        # Migrate existing bookmarks data
        rows = conn.execute("SELECT * FROM bookmarks").fetchall()
        row_dicts = [dict(r) for r in rows]

        # Get existing tags
        existing_tags = {r["name"]: r["id"] for r in conn.execute("SELECT id, name FROM tags").fetchall()}
        tag_names_by_id = {int(r["id"]): r["name"] for r in conn.execute("SELECT id, name FROM tags").fetchall()}
        tag_ids_by_bookmark = {}
        if _table_exists(conn, "bookmark_tags"):
            for tag_row in conn.execute("SELECT bookmark_id, tag_id FROM bookmark_tags").fetchall():
                tag_ids_by_bookmark.setdefault(int(tag_row["bookmark_id"]), []).append(int(tag_row["tag_id"]))

        _drop_legacy_v1_objects(conn)
    else:
        row_dicts = []
        existing_tags = {}

    # Create new schema
    conn.executescript(SCHEMA_V2)

    # Seed categories
    conn.executemany(
        "INSERT OR IGNORE INTO categories(slug, label, description, export_default, review_default) VALUES (?, ?, ?, ?, ?)",
        CATEGORY_SEED,
    )

    # Migrate existing tags before bookmark tag relationships are restored.
    for tag_name in existing_tags:
        conn.execute(
            "INSERT OR IGNORE INTO tags(name) VALUES (?)",
            (tag_name,),
        )

    # Migrate bookmarks
    author_map: dict[str, int] = {}
    link_map: dict[str, int] = {}
    entity_map: dict[tuple[str, str], int] = {}

    for row in row_dicts:
        import json

        status_id = row.get("status_id", "")
        author_handle = (row.get("author_handle") or "").lstrip("@")
        author_name = row.get("author_name") or ""
        tweet_text = row.get("tweet_text") or ""
        raw_text = row.get("raw_text") or tweet_text
        links_json = row.get("links_json", "[]")
        entities_json = row.get("entities_json", "[]")
        category = row.get("category", "misc")
        confidence = float(row.get("confidence", 0))
        summary = row.get("summary") or ""
        why_it_matters = row.get("why_it_matters") or ""
        needs_review = int(row.get("needs_review", 1))
        review_note = row.get("review_note") or ""
        captured_at = row.get("captured_at") or now
        created_at = row.get("created_at") or ""
        content_hash = row.get("content_hash") or ""
        status_url = row.get("status_url") or f"https://x.com/{author_handle}/status/{status_id}"
        old_bookmark_id = int(row.get("id") or 0)

        # Upsert author
        author_id: int | None = None
        if author_handle:
            if author_handle in author_map:
                author_id = author_map[author_handle]
            else:
                conn.execute(
                    "INSERT OR IGNORE INTO authors(handle, display_name, first_seen_at, last_seen_at) VALUES (?, ?, ?, ?)",
                    (author_handle, author_name, captured_at, captured_at),
                )
                author_row = conn.execute("SELECT id FROM authors WHERE handle = ?", (author_handle,)).fetchone()
                if author_row:
                    author_id = int(author_row["id"])
                    author_map[author_handle] = author_id

        # Insert bookmark
        conn.execute(
            """INSERT INTO bookmarks(id, status_id, status_url, author_id, author_name, author_handle,
               tweet_text, raw_text, created_at, captured_at, updated_at, content_hash,
               collection_source, needs_review, review_note, summary, why_it_matters)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                row.get("id"),
                status_id,
                status_url,
                author_id,
                author_name,
                author_handle,
                tweet_text,
                raw_text,
                created_at,
                captured_at,
                now,
                content_hash,
                "browser",
                needs_review,
                review_note,
                summary,
                why_it_matters,
            ),
        )

        bookmark_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])

        # Migrate links
        try:
            links = json.loads(links_json) if links_json else []
        except (json.JSONDecodeError, TypeError):
            links = []
        for url in links:
            if not url:
                continue
            if url in link_map:
                link_id = link_map[url]
            else:
                from urllib.parse import urlparse

                domain = ""
                try:
                    domain = urlparse(url).netloc.lower().removeprefix("www.")
                except Exception:
                    pass
                conn.execute(
                    "INSERT OR IGNORE INTO links(url, domain, first_seen_at, last_seen_at) VALUES (?, ?, ?, ?)",
                    (url, domain, captured_at, captured_at),
                )
                link_row = conn.execute("SELECT id FROM links WHERE url = ?", (url,)).fetchone()
                if link_row:
                    link_id = int(link_row["id"])
                    link_map[url] = link_id
                else:
                    continue
            conn.execute(
                "INSERT OR IGNORE INTO bookmark_links(bookmark_id, link_id, role) VALUES (?, ?, ?)",
                (bookmark_id, link_id, "mentioned"),
            )

        # Migrate entities
        try:
            entities = json.loads(entities_json) if entities_json else []
        except (json.JSONDecodeError, TypeError):
            entities = []
        for entity_name in entities:
            if not entity_name:
                continue
            key = (entity_name.lower().strip(), "other")
            if key in entity_map:
                entity_id = entity_map[key]
            else:
                conn.execute(
                    "INSERT OR IGNORE INTO entities(name, normalized_name, type, source) VALUES (?, ?, ?, ?)",
                    (entity_name, entity_name.lower().strip(), "other", "text-regex"),
                )
                entity_row = conn.execute(
                    "SELECT id FROM entities WHERE normalized_name = ? AND type = ?",
                    (entity_name.lower().strip(), "other"),
                ).fetchone()
                if entity_row:
                    entity_id = int(entity_row["id"])
                    entity_map[key] = entity_id
                else:
                    continue
            conn.execute(
                "INSERT OR IGNORE INTO bookmark_entities(bookmark_id, entity_id, salience) VALUES (?, ?, ?)",
                (bookmark_id, entity_id, 0.5),
            )

        # Migrate tag relationships.
        for tag_id in tag_ids_by_bookmark.get(old_bookmark_id, []):
            tag_name = tag_names_by_id.get(tag_id)
            if not tag_name:
                continue
            tag_row = conn.execute("SELECT id FROM tags WHERE name = ?", (tag_name,)).fetchone()
            if tag_row:
                conn.execute(
                    "INSERT OR IGNORE INTO bookmark_tags(bookmark_id, tag_id) VALUES (?, ?)",
                    (bookmark_id, int(tag_row["id"])),
                )

        # Migrate primary classification
        if category:
            conn.execute(
                """INSERT OR IGNORE INTO classifications
                   (bookmark_id, category_slug, confidence, method, rationale, is_primary, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (bookmark_id, category, confidence, "keyword", "migrated from v1", 1, now),
            )

    # Rebuild FTS
    conn.execute("INSERT INTO bookmarks_fts(bookmarks_fts) VALUES('rebuild')")

    apply_migration(conn, 2, "normalize schema to v2")
    repair_v2(conn)
    conn.commit()


def init_fresh(conn: sqlite3.Connection) -> None:
    """Initialize a fresh v2 database."""
    conn.executescript(SCHEMA_V2)
    conn.executemany(
        "INSERT OR IGNORE INTO categories(slug, label, description, export_default, review_default) VALUES (?, ?, ?, ?, ?)",
        CATEGORY_SEED,
    )
    apply_migration(conn, SCHEMA_VERSION, "fresh init v3")
    conn.commit()


def migrate_to_v3(conn: sqlite3.Connection) -> None:
    """Add durable full-content enrichment storage."""
    if get_schema_version(conn) >= 3:
        repair_v2(conn)
        return
    repair_v2(conn)
    apply_migration(conn, 3, "add content enrichments")
    conn.commit()


def migrate(conn: sqlite3.Connection) -> None:
    """Run all pending migrations."""
    version = get_schema_version(conn)
    if version == 0:
        # Check if tables exist (might be fresh v2 or legacy v1)
        has_bookmarks = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='bookmarks'"
        ).fetchone() is not None
        if has_bookmarks:
            # Check if it has the v1 schema (has 'category' column directly on bookmarks)
            cols = [r["name"] for r in conn.execute("PRAGMA table_info(bookmarks)").fetchall()]
            if "category" in cols:
                # Legacy v1 schema
                migrate_to_v2(conn)
                return
        # Fresh DB or already v2
        if version == 0:
            init_fresh(conn)
            return
    if version < 2:
        migrate_to_v2(conn)
    if get_schema_version(conn) < 3:
        migrate_to_v3(conn)
    repair_v2(conn)
