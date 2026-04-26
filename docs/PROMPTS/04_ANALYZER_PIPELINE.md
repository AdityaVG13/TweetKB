# Analyzer Pipeline Requirements

## Pipeline Stages
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

### Stages:
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

### Required Primary Categories:
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

### Minimum Local Classifier:
- keyword rules
- URL/domain rules
- repo/paper/model/tool detection
- author/domain priors
- fallback to existing heuristic

### Optional LLM Classifier:
- provider abstraction
- JSON schema output
- deterministic retry/repair
- disabled by default unless API key exists

Do not require paid API keys.

## Entity Extraction

Extract entities from text, links, and domains.

### Entity Types:
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

### Examples:
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

### Normalize Names:
- lower-case matching key
- strip punctuation
- canonical aliases
- `x.com` and `twitter.com` should normalize sensibly

## Embeddings

Add provider abstraction:

```
local-hash
local-model
openai
ollama
custom
```

Default must be `local-hash` or no external call.

### Commands:
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

### Minimum:
- category + entity overlap clustering
- domain/repo/model/paper clustering
- simple cosine similarity over local embeddings
- configurable similarity threshold
- cluster labels generated from top terms/entities

### Commands:
```bash
uv run tweetkb cluster
uv run tweetkb cluster --threshold 0.45
uv run tweetkb cluster --min-size 3
```

### Cluster Outputs:
- cluster label
- summary
- member bookmarks
- top entities
- top links
- top authors
- suggested project ideas

## Project Mining

Build `tweetkb projects` that identifies actionable project candidates.

### Inputs:
- clusters
- bookmarks
- entities
- categories
- links

### Output Project Idea Fields:
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

### Commands:
```bash
uv run tweetkb projects
uv run tweetkb projects --from-clusters
uv run tweetkb projects --min-evidence 3
uv run tweetkb projects export --vault ./obsidian-vault
```

Implement local heuristic version first.
Optional LLM version available but not required.

## Review System

Add review states:
- `new`
- `needs-review`
- `approved`
- `excluded`
- `archived`
- `project-candidate`

### Review Actions:
- approve bookmark
- exclude from export
- edit category
- add/remove tags
- add review note
- mark as project seed
- assign to cluster
- hide low-value item

### CLI:
```bash
uv run tweetkb review list
uv run tweetkb review list --category misc
uv run tweetkb review approve <status_id>
uv run tweetkb review exclude <status_id>
uv run tweetkb review tag <status_id> ai-agents
```

### HTTP API:
- `GET /api/bookmarks`
- `GET /api/bookmarks/:id`
- `PATCH /api/bookmarks/:id`
- `GET /api/categories`
- `GET /api/entities`
- `GET /api/clusters`
- `GET /api/projects`
- `POST /api/export`
