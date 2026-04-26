# Export System Requirements

## Export Adapters
Refactor exporter into adapters:
- Obsidian
- Logseq
- Generic Markdown
- JSONL
- CSV

## Export Profiles
```bash
uv run tweetkb export --adapter obsidian --vault ./obsidian-vault
uv run tweetkb export --adapter logseq --vault ./logseq-graph
uv run tweetkb export --adapter markdown --out ./exports/markdown
uv run tweetkb export --adapter jsonl --out ./exports/bookmarks.jsonl
uv run tweetkb export --adapter csv --out ./exports/bookmarks.csv
```

### Filters:
- include categories
- exclude categories
- exclude review
- include/exclude low confidence
- include/exclude project notes
- include/exclude cluster notes
- include/exclude raw tweets

Must support:
```bash
--exclude-category misc
--include-category ai-agents,coding,models
--exclude-review
--min-confidence 0.6
```

## Obsidian Note Design

Each bookmark note should include:
- YAML frontmatter
- source URL
- author
- category
- tags
- confidence
- review state
- exported timestamp
- summary
- why it matters
- tweet text
- links
- entities
- related bookmarks
- related clusters
- project candidates

### YAML Example:
```yaml
---
type: tweet-bookmark
status_id: "123"
source: "https://x.com/user/status/123"
author: "user"
categories:
  - ai-agents
  - browser-automation
confidence: 0.86
review_state: approved
exportable: true
---
```

Use Obsidian links:
```md
[[Topics/AI Agents]]
[[Entities/Browser-Harness]]
[[Projects/Local Agent Bookmark Graph]]
```

## Logseq Note Design

Prefer:
```md
- type:: tweet-bookmark
- status-id:: 123
- source:: https://x.com/user/status/123
- author:: [[Authors/user]]
- categories:: [[AI Agents]], [[Browser Automation]]
- summary:: ...
- why-it-matters:: ...
- tweet::
  - Original text here
- links::
  - https://...
- entities::
  - [[Browser-Harness]]
```

## Custom Compression Engine

### File Extensions:
- `.tweetzip`
- `.twz`

### TweetZip v1 Container:
```
magic:      "TWZ1"
flags:      u16
record_ct:  varint
dict_len:   varint
dict_blob:  bytes
records:    repeated compressed records
checksum:   u64
```

### Record Model:
```
record_id_delta: varint
field_mask:      varint
status_id:       delta or string table reference
author:          dictionary/string table reference
url:             dictionary/string table reference
text:            compressed token stream
metadata:        optional JSON-ish compact block
```

### Compression Techniques:
1. **Static domain dictionary**:
   - `https://`, `http://`, `x.com/`, `twitter.com/`
   - `github.com/`, `huggingface.co/`, `arxiv.org/`
   - `openai.com/`, `anthropic.com/`
   - common AI/model/tool tokens

2. **Per-archive dynamic dictionary**:
   - authors, domains, repeated URL prefixes
   - repeated entity names, category labels
   - top N token n-grams

3. **Token stream encoding**:
   - split text into words, whitespace, punctuation, URLs, handles, hashtags
   - dictionary references for frequent tokens
   - raw literals for rare tokens
   - varint lengths

4. **Delta encoding**:
   - numeric status IDs as delta encoded when sorted
   - timestamps delta encoded if present
   - repeated authors/domains use dictionary IDs

5. **Checksum**: CRC32 or FNV-1a

### Required CLI:
```bash
uv run tweetkb compress export --out ./exports/bookmarks.twz
uv run tweetkb compress inspect ./exports/bookmarks.twz
uv run tweetkb compress decompress ./exports/bookmarks.twz --out ./exports/bookmarks.jsonl
uv run tweetkb compress benchmark
uv run tweetkb compress verify ./exports/bookmarks.twz
```

### Python API:
```python
from tweetkb.compress import encode_records, decode_records, inspect_archive
```

### Benchmark Output:
```
input_jsonl_bytes
tweetzip_bytes
sqlite_bytes
gzip_jsonl_bytes if available
compression_ratio_vs_jsonl
compression_ratio_vs_sqlite
encode_ms
decode_ms
records_per_second
roundtrip_ok
```

## Compact Command
```bash
uv run tweetkb compact
uv run tweetkb compact --dry-run
uv run tweetkb compact --vacuum
uv run tweetkb compact --report
uv run tweetkb compact --backup ./backups/bookmarks.sqlite3.zst
```

### Minimum `compact --report` Output:
```
database_path
file_size_bytes
page_size
page_count
freelist_count
bookmark_count
link_count
entity_count
embedding_count
estimated_reclaimable_bytes
```
