# Data Model

## Schema Version

Current: **version 2** (2026-04-26)
Migration system tracks applied migrations in `schema_migrations` table.

## Core Tables

### bookmarks
Primary tweet storage. One row per bookmarked tweet.

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PRIMARY KEY | Auto-increment |
| status_id | TEXT UNIQUE NOT NULL | Tweet ID, e.g. "1899012345678901234" |
| status_url | TEXT NOT NULL | Normalized to https://x.com/handle/status/id |
| author_id | INTEGER NULL | FK -> authors.id |
| author_name | TEXT | Display name |
| author_handle | TEXT | @handle without @ |
| tweet_text | TEXT NOT NULL DEFAULT '' | Cleaned tweet content |
| raw_text | TEXT NOT NULL DEFAULT '' | Full DOM extraction |
| created_at | TEXT | Tweet creation time (from Twitter) |
| captured_at | TEXT NOT NULL | When we saved it |
| updated_at | TEXT NOT NULL | Last modification |
| content_hash | TEXT NOT NULL | SHA-256 of content for change detection |
| collection_source | TEXT NOT NULL DEFAULT 'browser' | 'browser', 'api', 'rss' |
| collection_run_id | TEXT | FK -> collection_runs.id |
| is_archived | INTEGER NOT NULL DEFAULT 0 | Soft-delete |
| is_deleted | INTEGER NOT NULL DEFAULT 0 | Hard-delete |
| is_exportable | INTEGER NOT NULL DEFAULT 1 | Include in exports |
| needs_review | INTEGER NOT NULL DEFAULT 1 | Review queue flag |
| review_note | TEXT NOT NULL DEFAULT '' | User review note |
| review_state | TEXT NOT NULL DEFAULT 'new' | new, needs-review, approved, excluded, archived, project-candidate |
| summary | TEXT NOT NULL DEFAULT '' | Auto-generated summary |
| why_it_matters | TEXT NOT NULL DEFAULT '' | Auto-generated rationale |

**Indexes:**
- `idx_bookmarks_status_id` on `status_id`
- `idx_bookmarks_author_handle` on `author_handle`
- `idx_bookmarks_category_slug` on `category_slug` (legacy, deprecated)
- `idx_bookmarks_review_state` on `review_state`
- `idx_bookmarks_reviewable` on `(is_exportable, needs_review, is_deleted)`
- `idx_bookmarks_captured` on `captured_at DESC`

### authors
Normalized author/account data.

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PRIMARY KEY | |
| handle | TEXT UNIQUE | Without @ |
| display_name | TEXT | |
| profile_url | TEXT | |
| first_seen_at | TEXT | |
| last_seen_at | TEXT | |
| bookmark_count | INTEGER DEFAULT 0 | Denormalized for speed |

### links
Normalized link data.

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PRIMARY KEY | |
| url | TEXT UNIQUE NOT NULL | Canonical URL |
| normalized_url | TEXT | Without tracking params |
| domain | TEXT | e.g. "github.com" |
| title | TEXT | |
| description | TEXT | |
| content_type | TEXT | e.g. "text/html" |
| first_seen_at | TEXT | |
| last_seen_at | TEXT | |

### bookmark_links
Many-to-many join between bookmarks and links.

| Column | Type | Notes |
|--------|------|-------|
| bookmark_id | INTEGER NOT NULL | FK -> bookmarks.id |
| link_id | INTEGER NOT NULL | FK -> links.id |
| role | TEXT NOT NULL DEFAULT 'mentioned' | 'mentioned', 'embedded', 'quoted' |
| PRIMARY KEY | (bookmark_id, link_id) | |

### categories
Taxonomy categories.

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PRIMARY KEY | |
| slug | TEXT UNIQUE NOT NULL | URL-safe identifier |
| label | TEXT NOT NULL | Human-readable |
| description | TEXT | |
| export_default | INTEGER NOT NULL DEFAULT 1 | Include in exports by default |
| review_default | INTEGER NOT NULL DEFAULT 0 | Needs review by default |

**Primary Categories (seed data):**
- ai-agents, coding, models, evals, tools, design, infra, papers, prompts, workflows, product-ideas, business, security, data, robotics, voice-audio, vision, browser-automation, local-first, open-source, misc

### classifications
Multi-label classification results per bookmark.

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PRIMARY KEY | |
| bookmark_id | INTEGER NOT NULL | FK -> bookmarks.id |
| category_slug | TEXT NOT NULL | FK -> categories.slug |
| confidence | REAL NOT NULL | 0.0 - 1.0 |
| method | TEXT NOT NULL | 'keyword', 'url-rule', 'llm', 'heuristic' |
| rationale | TEXT | Why this category was assigned |
| is_primary | INTEGER NOT NULL DEFAULT 0 | Primary category flag |
| created_at | TEXT NOT NULL | |

**Indexes:**
- `idx_classifications_bookmark` on `bookmark_id`
- `idx_classifications_category` on `category_slug`
- `UNIQUE(bookmark_id, category_slug)`

### entities
Extracted entities from text and links.

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PRIMARY KEY | |
| name | TEXT NOT NULL | Raw extracted name |
| normalized_name | TEXT NOT NULL | Lowercase, stripped |
| type | TEXT NOT NULL | person, company, product, model, paper, repo, framework, library, protocol, dataset, benchmark, concept, domain, language, cloud, database, app, other |
| source | TEXT NOT NULL | 'text-regex', 'url-pattern', 'llm', 'alias-table' |
| UNIQUE | (normalized_name, type) | |

### bookmark_entities
Many-to-many join.

| Column | Type | Notes |
|--------|------|-------|
| bookmark_id | INTEGER NOT NULL | FK -> bookmarks.id |
| entity_id | INTEGER NOT NULL | FK -> entities.id |
| salience | REAL NOT NULL DEFAULT 0.5 | 0.0 - 1.0 |
| evidence | TEXT | Text snippet showing entity |
| PRIMARY KEY | (bookmark_id, entity_id) | |

### tags
User-defined tags.

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PRIMARY KEY | |
| name | TEXT UNIQUE NOT NULL | |

### bookmark_tags
Many-to-many join.

| Column | Type | Notes |
|--------|------|-------|
| bookmark_id | INTEGER NOT NULL | FK -> bookmarks.id |
| tag_id | INTEGER NOT NULL | FK -> tags.id |
| PRIMARY KEY | (bookmark_id, tag_id) | |

### embeddings
Bookmark embedding vectors.

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PRIMARY KEY | |
| bookmark_id | INTEGER NOT NULL | FK -> bookmarks.id |
| provider | TEXT NOT NULL | 'local-hash', 'ollama', 'openai' |
| model | TEXT NOT NULL | e.g. "nomic-embed-text" |
| dims | INTEGER NOT NULL | Vector dimensionality |
| vector_json | TEXT NOT NULL | JSON array of floats |
| content_hash | TEXT NOT NULL | Source content hash for change detection |
| updated_at | TEXT NOT NULL | |
| UNIQUE | (bookmark_id, provider, model) | |

### clusters
Topic clusters.

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PRIMARY KEY | |
| slug | TEXT UNIQUE NOT NULL | URL-safe label |
| label | TEXT NOT NULL | Human-readable name |
| summary | TEXT | Auto-generated description |
| method | TEXT NOT NULL | 'heuristic', 'llm' |
| created_at | TEXT NOT NULL | |
| updated_at | TEXT NOT NULL | |

### cluster_members
Bookmark-cluster membership.

| Column | Type | Notes |
|--------|------|-------|
| cluster_id | INTEGER NOT NULL | FK -> clusters.id |
| bookmark_id | INTEGER NOT NULL | FK -> bookmarks.id |
| score | REAL NOT NULL | Similarity/probability score |
| PRIMARY KEY | (cluster_id, bookmark_id) | |

### project_ideas
Generated project candidates.

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PRIMARY KEY | |
| slug | TEXT UNIQUE NOT NULL | URL-safe title |
| title | TEXT NOT NULL | |
| one_liner | TEXT NOT NULL | One sentence summary |
| problem | TEXT | What problem it solves |
| audience | TEXT | Target user |
| why_now | TEXT | Why this is relevant now |
| implementation_notes | TEXT | Build path |
| source_cluster_id | INTEGER | FK -> clusters.id |
| confidence | REAL NOT NULL | 0.0 - 1.0 |
| status | TEXT NOT NULL DEFAULT 'candidate' | candidate, in-progress, shipped, dismissed |
| created_at | TEXT NOT NULL | |
| updated_at | TEXT NOT NULL | |

### project_sources
Evidence bookmarks for projects.

| Column | Type | Notes |
|--------|------|-------|
| project_id | INTEGER NOT NULL | FK -> project_ideas.id |
| bookmark_id | INTEGER NOT NULL | FK -> bookmarks.id |
| role | TEXT NOT NULL DEFAULT 'evidence' | 'evidence', 'reference', 'inspiration' |
| PRIMARY KEY | (project_id, bookmark_id) | |

### export_profiles
Saved export configurations.

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PRIMARY KEY | |
| name | TEXT UNIQUE NOT NULL | Profile name |
| adapter | TEXT NOT NULL | 'obsidian', 'logseq', 'markdown', 'jsonl', 'csv' |
| vault_path | TEXT | Export root path |
| include_categories_json | TEXT NOT NULL DEFAULT '[]' | |
| exclude_categories_json | TEXT NOT NULL DEFAULT '[]' | |
| exclude_review | INTEGER NOT NULL DEFAULT 0 | |
| include_projects | INTEGER NOT NULL DEFAULT 1 | |
| include_clusters | INTEGER NOT NULL DEFAULT 1 | |
| created_at | TEXT NOT NULL | |
| updated_at | TEXT NOT NULL | |

### export_runs
Export execution log.

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PRIMARY KEY | |
| profile_id | INTEGER | FK -> export_profiles.id |
| adapter | TEXT NOT NULL | |
| output_path | TEXT NOT NULL | |
| exported_count | INTEGER NOT NULL | |
| skipped_count | INTEGER NOT NULL | |
| created_at | TEXT NOT NULL | |

### collection_runs
Collection session log.

| Column | Type | Notes |
|--------|------|-------|
| id | TEXT PRIMARY KEY | UUID |
| source | TEXT NOT NULL | 'browser-harness', 'apple-events', 'api' |
| started_at | TEXT NOT NULL | |
| finished_at | TEXT | |
| status | TEXT NOT NULL | 'running', 'completed', 'failed' |
| seen_count | INTEGER NOT NULL DEFAULT 0 | |
| changed_count | INTEGER NOT NULL DEFAULT 0 | |
| unchanged_count | INTEGER NOT NULL DEFAULT 0 | |
| error | TEXT | |
| metadata_json | TEXT NOT NULL DEFAULT '{}' | |

### schema_migrations
Migration tracking.

| Column | Type | Notes |
|--------|------|-------|
| version | INTEGER PRIMARY KEY | |
| name | TEXT NOT NULL | Migration name |
| applied_at | TEXT NOT NULL | ISO timestamp |

## FTS

### bookmarks_fts
Full-text search virtual table over tweet content.

```sql
CREATE VIRTUAL TABLE bookmarks_fts USING fts5(
  tweet_text, summary, author_name, author_handle,
  content='bookmarks', content_rowid='id'
);
```

Triggers keep it in sync with bookmarks INSERT/UPDATE/DELETE.

## Legacy Columns (v1 schema, read-only migration)

The original schema had single-category `bookmarks.category` and JSON columns for enrichment. The migration system copies this data into the new normalized tables on upgrade.

| Old Column | Migration |
|------------|-----------|
| category TEXT | -> classifications (primary only) |
| confidence REAL | -> classifications.confidence |
| summary TEXT | -> bookmarks.summary |
| why_it_matters TEXT | -> bookmarks.why_it_matters |
| use_cases_json TEXT | -> (dropped, regenerated) |
| entities_json TEXT | -> entities + bookmark_entities |
| links_json TEXT | -> links + bookmark_links |
