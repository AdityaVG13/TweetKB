# Export Adapters

## Overview

TwitterOrganizer exports bookmarks to multiple knowledge tools. Exports are adapters that read from SQLite and write to target format. The SQLite DB remains the source of truth.

## Adapters

### Obsidian (`obsidian`)

Exports bookmark notes with YAML frontmatter and Markdown body.

**Output structure:**
```
vault/
  Bookmarks/
    {status_id}-{slug}.md     # One note per bookmark
  Topics/
    {category-slug}.md        # Index per category
  Entities/
    {entity-name}.md          # Index per entity (optional)
  Projects/
    {project-slug}.md         # Project idea notes (optional)
```

**Bookmark note format:**
```markdown
---
type: tweet-bookmark
status_id: "1899012345678901234"
source: https://x.com/username/status/1899012345678901234
author: username
categories:
  - ai-agents
  - browser-automation
confidence: 0.86
review_state: approved
exportable: true
captured: 2026-04-26T12:00:00
---

# Bookmark Summary Here

Source: [x.com](https://x.com/username/status/1899012345678901234)
Author: @username
Categories: [[Topics/AI Agents]], [[Topics/Browser Automation]]

## Summary
Auto-generated summary text...

## Why It Matters
Auto-generated rationale...

## Tweet Text
Original tweet content...

## Links
- https://github.com/example/repo
- https://arxiv.org/paper/1234

## Entities
- [[Entities/Browser-Harness]]
- [[Entities/MCP]]

## Related
- [[Bookmarks/123-another-bookmark|Another Bookmark Title]]
```

### Logseq (`logseq`)

Logseq reads Markdown with property syntax. No app-specific link syntax.

**Output structure:**
```
vault/
  pages/
    {status_id}-{slug}.md
  journals/           # Optional
```

**Bookmark format:**
```markdown
- type:: tweet-bookmark
- status-id:: 1899012345678901234
- source:: https://x.com/username/status/1899012345678901234
- author:: [[username]]
- categories:: [[AI Agents]], [[Browser Automation]]
- confidence:: 0.86
- review-state:: approved
- captured:: 2026-04-26

# Bookmark Summary Here

## Summary
Auto-generated summary...

## Tweet
> Original tweet text here

## Links
- https://github.com/example/repo
- https://arxiv.org/paper/1234

## Entities
- Browser-Harness
- MCP

## Related
- [[Another Bookmark Title]]
```

### Generic Markdown (`markdown`)

Plain Markdown with standard YAML frontmatter. Avoids Obsidian/Logseq specific syntax.

**Output structure:**
```
output/
  bookmarks/
    {status_id}-{slug}.md
  topics/
    {category}.md
  projects/
    {project}.md
  index.md
```

### JSONL (`jsonl`)

One JSON object per line. Good for data pipelines, spreadsheets via CSV conversion.

**Record format:**
```json
{"status_id":"1899012345678901234","status_url":"https://x.com/username/status/1899012345678901234","author_handle":"username","author_name":"Display Name","tweet_text":"...","summary":"...","categories":["ai-agents","browser-automation"],"confidence":0.86,"review_state":"approved","entities":["Browser-Harness","MCP"],"links":["https://github.com/..."],"tags":["ai","automation"],"captured_at":"2026-04-26T12:00:00Z"}
```

### CSV (`csv`)

Flattened table suitable for spreadsheets.

**Columns:**
```
status_id,status_url,author_handle,author_name,tweet_text,summary,primary_category,confidence,review_state,categories,entities,links,captured_at
```

## Export Filters

All adapters support these filters:

| Flag | Effect |
|------|--------|
| `--include-category cats` | Only these categories |
| `--exclude-category cats` | Exclude these categories |
| `--exclude-review` | Skip bookmarks needing review |
| `--min-confidence N` | Skip below this confidence |
| `--include-projects` | Include project notes (Obsidian/Logseq) |
| `--include-clusters` | Include cluster notes (Obsidian/Logseq) |

## Export Profiles

Saved configurations via `tweetkb export --save-profile my-profile`.

```bash
tweetkb export --adapter obsidian --vault ./vault --exclude-category misc --exclude-review --save-profile clean-vault
tweetkb export --profile clean-vault
```

## Overwrite Behavior

- Adapters write directly to target directory
- Existing files are overwritten with updated content
- Idempotent: re-running produces same output for unchanged bookmarks
- Use `--dry-run` to preview without writing

## Privacy

Exported vault contains bookmark text. Keep vault path out of git.
