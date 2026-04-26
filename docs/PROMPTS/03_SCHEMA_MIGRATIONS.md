# Schema & Migrations Requirements

## Migration Framework
Create a migration system. Do not rely forever on one large `CREATE TABLE IF NOT EXISTS` string.

Implement:
- `schema_migrations(version integer primary key, name text, applied_at text)`
- ordered migration functions or SQL files
- `tweetkb migrate`
- `tweetkb init` should run migrations
- migrations must be idempotent
- tests for fresh DB and existing DB upgrades

## Required Schema Tables

### bookmarks
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

### authors
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

### links
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

### bookmark_links
```sql
bookmark_links
  bookmark_id integer not null
  link_id integer not null
  role text not null default 'mentioned'
  primary key(bookmark_id, link_id)
```

### categories
```sql
categories
  id integer primary key
  slug text unique not null
  label text not null
  description text
  export_default integer not null default 1
  review_default integer not null default 0
```

### classifications
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

### bookmark_category
```sql
bookmark_category
  bookmark_id integer not null
  category_slug text not null
  confidence real not null
  is_primary integer not null default 0
  primary key(bookmark_id, category_slug)
```

### entities
```sql
entities
  id integer primary key
  name text not null
  normalized_name text not null
  type text not null
  source text not null
  unique(normalized_name, type)
```

### bookmark_entities
```sql
bookmark_entities
  bookmark_id integer not null
  entity_id integer not null
  salience real not null default 0.5
  evidence text
  primary key(bookmark_id, entity_id)
```

### tags
```sql
tags
  id integer primary key
  name text unique not null
```

### bookmark_tags
```sql
bookmark_tags
  bookmark_id integer not null
  tag_id integer not null
  primary key(bookmark_id, tag_id)
```

### embeddings
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

### clusters
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

### cluster_members
```sql
cluster_members
  cluster_id integer not null
  bookmark_id integer not null
  score real not null
  primary key(cluster_id, bookmark_id)
```

### project_ideas
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

### project_sources
```sql
project_sources
  project_id integer not null
  bookmark_id integer not null
  role text not null default 'evidence'
  primary key(project_id, bookmark_id)
```

### export_profiles
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

### export_runs
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

### collection_runs
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
