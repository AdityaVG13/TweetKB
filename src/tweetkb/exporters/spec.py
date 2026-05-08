from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..util import ensure_dir


def export_spec(
    store,
    out_dir: Path,
    include_categories: set[str] | None = None,
    exclude_categories: set[str] | None = None,
    exclude_review: bool = False,
    min_confidence: float = 0.0,
    include_projects: bool = True,
    include_clusters: bool = False,
) -> tuple[int, int]:
    """Export bookmarks as a static interactive HTML analysis spec."""
    out_dir = ensure_dir(Path(out_dir))
    include_categories = {c.strip() for c in (include_categories or set()) if c.strip()}
    exclude_categories = {c.strip() for c in (exclude_categories or set()) if c.strip()}

    exported = 0
    skipped = 0
    records: list[dict[str, Any]] = []
    category_counts: dict[str, int] = {}
    entity_counts: dict[str, int] = {}

    for row in store.list_bookmarks():
        bookmark_id = int(row["id"])
        if row["is_deleted"]:
            skipped += 1
            continue

        classifs = store.get_bookmark_classifications(bookmark_id)
        primary = _primary_category(classifs)
        confidence = _primary_confidence(classifs)
        if include_categories and primary not in include_categories:
            skipped += 1
            continue
        if exclude_categories and primary in exclude_categories:
            skipped += 1
            continue
        if exclude_review and row["needs_review"]:
            skipped += 1
            continue
        if confidence < min_confidence:
            skipped += 1
            continue

        record = _bookmark_record(store, row, classifs)
        records.append(record)
        category_counts[primary] = category_counts.get(primary, 0) + 1
        for entity in record["entities"]:
            name = entity["name"]
            entity_counts[name] = entity_counts.get(name, 0) + 1
        exported += 1

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "exported": exported,
        "skipped": skipped,
        "include_projects": include_projects,
        "include_clusters": include_clusters,
        "categories": category_counts,
        "entities": dict(sorted(entity_counts.items(), key=lambda item: (-item[1], item[0]))[:50]),
        "bookmarks": records,
    }
    (out_dir / "index.html").write_text(_render_html(payload), encoding="utf-8")
    return exported, skipped


def _bookmark_record(store, row, classifs) -> dict[str, Any]:
    bookmark_id = int(row["id"])
    enrichments = [
        {
            "source_type": enrichment["source_type"],
            "source_url": enrichment["source_url"],
            "title": enrichment["title"] or enrichment["source_url"],
            "content_text": enrichment["content_text"] or "",
            "metadata": _loads_metadata(enrichment["metadata_json"]),
        }
        for enrichment in store.get_content_enrichments(bookmark_id)
    ]
    return {
        "id": bookmark_id,
        "status_id": str(row["status_id"]),
        "url": row["status_url"],
        "author": {
            "name": row["author_name"] or "",
            "handle": row["author_handle"] or "",
        },
        "created_at": row["created_at"] or "",
        "captured_at": row["captured_at"] or "",
        "summary": row["summary"] or "",
        "why_it_matters": row["why_it_matters"] or "",
        "tweet_text": row["tweet_text"] or "",
        "raw_text": row["raw_text"] or "",
        "review_state": row["review_state"] or "",
        "needs_review": bool(row["needs_review"]),
        "is_exportable": bool(row["is_exportable"]),
        "categories": [
            {
                "slug": c["category_slug"],
                "confidence": float(c["confidence"]),
                "method": c["method"],
                "rationale": c["rationale"],
                "is_primary": bool(c["is_primary"]),
            }
            for c in classifs
        ],
        "primary_category": _primary_category(classifs),
        "primary_confidence": _primary_confidence(classifs),
        "links": [{"url": link["url"], "domain": link["domain"]} for link in store.get_bookmark_links(bookmark_id)],
        "entities": [
            {
                "name": entity["name"],
                "type": entity["type"],
                "source": entity["source"],
                "evidence": entity["evidence"],
            }
            for entity in store.get_bookmark_entities(bookmark_id)
        ],
        "tags": store.get_bookmark_tags(bookmark_id),
        "enrichments": enrichments,
        "media": _media_from_enrichments(enrichments),
    }


def _primary_category(classifs) -> str:
    for c in classifs:
        if c["is_primary"]:
            return c["category_slug"]
    return classifs[0]["category_slug"] if classifs else "misc"


def _primary_confidence(classifs) -> float:
    for c in classifs:
        if c["is_primary"]:
            return float(c["confidence"])
    return float(classifs[0]["confidence"]) if classifs else 0.0


def _loads_metadata(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        loaded = json.loads(value)
        return loaded if isinstance(loaded, dict) else {}
    except json.JSONDecodeError:
        return {}


def _media_from_enrichments(enrichments: list[dict[str, Any]]) -> list[dict[str, str]]:
    media: list[dict[str, str]] = []
    seen: set[str] = set()
    for enrichment in enrichments:
        for item in enrichment.get("metadata", {}).get("media", []) or []:
            if not isinstance(item, dict):
                continue
            url = item.get("url") or item.get("src") or ""
            if not url or url in seen:
                continue
            seen.add(url)
            media.append(
                {
                    "url": url,
                    "alt": item.get("alt") or "",
                    "source_type": enrichment.get("source_type", ""),
                }
            )
    return media


def _render_html(payload: dict[str, Any]) -> str:
    data = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>TweetKB Interactive Analysis Spec</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f7f5ef;
      --panel: #ffffff;
      --ink: #171717;
      --muted: #66645e;
      --line: #ded8ca;
      --accent: #0f766e;
      --accent-2: #7c2d12;
      --chip: #ebe6d8;
      --shadow: 0 12px 32px rgba(24, 24, 20, 0.08);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font: 15px/1.45 ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    a {{ color: var(--accent); }}
    header {{
      padding: 28px clamp(18px, 4vw, 48px) 18px;
      border-bottom: 1px solid var(--line);
      background: #fffdf8;
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: clamp(28px, 4vw, 42px);
      letter-spacing: 0;
    }}
    h2, h3 {{ letter-spacing: 0; }}
    .subhead {{ max-width: 900px; color: var(--muted); }}
    .toolbar {{
      display: grid;
      grid-template-columns: minmax(220px, 1fr) repeat(2, minmax(150px, 220px));
      gap: 12px;
      padding: 18px clamp(18px, 4vw, 48px);
      border-bottom: 1px solid var(--line);
      background: #fbf8f1;
      position: sticky;
      top: 0;
      z-index: 2;
    }}
    input, select {{
      width: 100%;
      min-height: 40px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: var(--panel);
      color: var(--ink);
      padding: 8px 10px;
      font: inherit;
    }}
    main {{
      display: grid;
      grid-template-columns: minmax(220px, 290px) minmax(0, 1fr);
      gap: 22px;
      padding: 22px clamp(18px, 4vw, 48px) 40px;
    }}
    aside {{
      align-self: start;
      position: sticky;
      top: 92px;
    }}
    .metric-grid {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
      margin-bottom: 18px;
    }}
    .metric, .side-panel, .card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
    }}
    .metric {{ padding: 12px; }}
    .metric strong {{ display: block; font-size: 24px; }}
    .metric span {{ color: var(--muted); font-size: 12px; }}
    .side-panel {{ padding: 14px; margin-bottom: 14px; box-shadow: none; }}
    .side-panel h2 {{ margin: 0 0 10px; font-size: 15px; }}
    .rank-list {{ display: grid; gap: 8px; }}
    .rank-row {{ display: flex; justify-content: space-between; gap: 10px; color: var(--muted); }}
    .cards {{ display: grid; gap: 16px; }}
    .card {{ overflow: hidden; }}
    .card-head {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 14px;
      padding: 18px;
      border-bottom: 1px solid var(--line);
    }}
    .card h2 {{ margin: 0 0 8px; font-size: 20px; }}
    .meta {{ color: var(--muted); font-size: 13px; display: flex; gap: 12px; flex-wrap: wrap; }}
    .score {{ font-variant-numeric: tabular-nums; color: var(--accent-2); font-weight: 700; }}
    .card-body {{ padding: 0 18px 18px; }}
    .chips {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }}
    .chip {{
      display: inline-flex;
      align-items: center;
      min-height: 26px;
      border-radius: 999px;
      background: var(--chip);
      padding: 4px 9px;
      color: #35332d;
      font-size: 12px;
    }}
    details {{
      border-top: 1px solid var(--line);
      padding: 12px 0;
    }}
    summary {{ cursor: pointer; font-weight: 700; }}
    .section-text {{
      margin-top: 10px;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      color: #292721;
    }}
    .source-grid {{ display: grid; gap: 10px; margin-top: 10px; }}
    .source-item {{
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 10px;
      background: #fffdf8;
    }}
    .empty {{ padding: 32px; color: var(--muted); text-align: center; }}
    @media (max-width: 840px) {{
      .toolbar {{ grid-template-columns: 1fr; position: static; }}
      main {{ grid-template-columns: 1fr; }}
      aside {{ position: static; }}
      .card-head {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>TweetKB Interactive Analysis Spec</h1>
    <p class="subhead">Searchable local analysis of exported bookmarks, categories, entities, captured thread context, followed links, and visible media metadata.</p>
  </header>
  <section class="toolbar" aria-label="Filters">
    <input id="search" type="search" placeholder="Search summary, tweet text, entities, links">
    <select id="category"><option value="">All categories</option></select>
    <select id="review">
      <option value="">All review states</option>
      <option value="needs-review">Needs review</option>
      <option value="reviewed">Reviewed</option>
      <option value="approved">Approved</option>
      <option value="excluded">Excluded</option>
    </select>
  </section>
  <main>
    <aside>
      <section class="metric-grid">
        <div class="metric"><strong id="metric-exported">0</strong><span>exported</span></div>
        <div class="metric"><strong id="metric-visible">0</strong><span>visible</span></div>
      </section>
      <section class="side-panel">
        <h2>Categories</h2>
        <div id="category-ranks" class="rank-list"></div>
      </section>
      <section class="side-panel">
        <h2>Top Entities</h2>
        <div id="entity-ranks" class="rank-list"></div>
      </section>
    </aside>
    <section>
      <div id="cards" class="cards"></div>
    </section>
  </main>
  <script id="tweetkb-data" type="application/json">{data}</script>
  <script>
    const data = JSON.parse(document.getElementById('tweetkb-data').textContent);
    const state = {{ search: '', category: '', review: '' }};
    const el = (tag, attrs = {{}}, children = []) => {{
      const node = document.createElement(tag);
      for (const [key, value] of Object.entries(attrs)) {{
        if (key === 'class') node.className = value;
        else if (key === 'text') node.textContent = value;
        else if (key === 'href') {{
          node.href = value;
          node.target = '_blank';
          node.rel = 'noopener noreferrer';
        }} else node.setAttribute(key, value);
      }}
      for (const child of children) node.append(child);
      return node;
    }};
    const percent = (value) => `${{Math.round((value || 0) * 100)}}%`;
    const textBlob = (b) => [
      b.summary, b.why_it_matters, b.tweet_text, b.raw_text,
      b.primary_category, ...(b.tags || []),
      ...(b.entities || []).map(e => `${{e.name}} ${{e.type}}`),
      ...(b.links || []).map(l => l.url),
      ...(b.enrichments || []).map(e => `${{e.title}} ${{e.source_url}} ${{e.content_text}}`)
    ].join(' ').toLowerCase();
    function init() {{
      document.getElementById('metric-exported').textContent = data.exported;
      const categories = Object.keys(data.categories || {{}}).sort();
      for (const category of categories) {{
        document.getElementById('category').append(el('option', {{ value: category, text: category }}));
      }}
      renderRanks('category-ranks', data.categories || {{}});
      renderRanks('entity-ranks', data.entities || {{}});
      document.getElementById('search').addEventListener('input', event => {{
        state.search = event.target.value.trim().toLowerCase();
        render();
      }});
      document.getElementById('category').addEventListener('change', event => {{
        state.category = event.target.value;
        render();
      }});
      document.getElementById('review').addEventListener('change', event => {{
        state.review = event.target.value;
        render();
      }});
      render();
    }}
    function renderRanks(target, values) {{
      const root = document.getElementById(target);
      root.replaceChildren();
      for (const [name, count] of Object.entries(values).slice(0, 14)) {{
        root.append(el('div', {{ class: 'rank-row' }}, [el('span', {{ text: name }}), el('strong', {{ text: String(count) }})]));
      }}
    }}
    function filteredBookmarks() {{
      return data.bookmarks.filter(bookmark => {{
        if (state.category && bookmark.primary_category !== state.category) return false;
        if (state.review === 'needs-review' && !bookmark.needs_review) return false;
        if (state.review === 'reviewed' && bookmark.needs_review) return false;
        if (state.review === 'approved' && bookmark.review_state !== 'approved') return false;
        if (state.review === 'excluded' && bookmark.review_state !== 'excluded') return false;
        if (state.search && !textBlob(bookmark).includes(state.search)) return false;
        return true;
      }});
    }}
    function render() {{
      const root = document.getElementById('cards');
      const rows = filteredBookmarks();
      document.getElementById('metric-visible').textContent = rows.length;
      root.replaceChildren();
      if (!rows.length) {{
        root.append(el('div', {{ class: 'empty', text: 'No bookmarks match the current filters.' }}));
        return;
      }}
      for (const bookmark of rows) root.append(renderCard(bookmark));
    }}
    function renderCard(bookmark) {{
      const title = bookmark.summary || bookmark.tweet_text || bookmark.status_id;
      const head = el('div', {{ class: 'card-head' }}, [
        el('div', {{}}, [
          el('h2', {{ text: title }}),
          el('div', {{ class: 'meta' }}, [
            el('span', {{ text: `@${{bookmark.author.handle || 'unknown'}}` }}),
            el('span', {{ text: bookmark.primary_category }}),
            el('span', {{ text: bookmark.needs_review ? 'needs review' : bookmark.review_state || 'reviewed' }}),
          ]),
        ]),
        el('div', {{ class: 'score', text: percent(bookmark.primary_confidence) }}),
      ]);
      const body = el('div', {{ class: 'card-body' }});
      body.append(el('div', {{ class: 'chips' }}, [
        ...(bookmark.tags || []).slice(0, 10).map(tag => el('span', {{ class: 'chip', text: `#${{tag}}` }})),
        ...(bookmark.entities || []).slice(0, 8).map(entity => el('span', {{ class: 'chip', text: entity.name }})),
      ]));
      body.append(section('Analysis', [
        ['Summary', bookmark.summary],
        ['Why it matters', bookmark.why_it_matters],
        ['Primary category', `${{bookmark.primary_category}} (${{percent(bookmark.primary_confidence)}})`],
      ]));
      body.append(textSection('Tweet Text', bookmark.tweet_text || bookmark.raw_text));
      body.append(linkSection('Followed / Mentioned Links', bookmark.links || []));
      body.append(enrichmentSection(bookmark.enrichments || []));
      body.append(mediaSection(bookmark.media || []));
      body.append(entitySection(bookmark.entities || []));
      body.append(el('p', {{}}, [el('a', {{ href: bookmark.url, text: 'Open source bookmark' }})]));
      return el('article', {{ class: 'card' }}, [head, body]);
    }}
    function section(title, rows) {{
      const details = el('details', {{ open: '' }}, [el('summary', {{ text: title }})]);
      const box = el('div', {{ class: 'source-grid' }});
      for (const [label, value] of rows) {{
        if (!value) continue;
        box.append(el('div', {{ class: 'source-item' }}, [
          el('strong', {{ text: label }}),
          el('div', {{ class: 'section-text', text: value }}),
        ]));
      }}
      details.append(box);
      return details;
    }}
    function textSection(title, text) {{
      const details = el('details', {{}}, [el('summary', {{ text: title }})]);
      details.append(el('div', {{ class: 'section-text', text: text || 'No text captured.' }}));
      return details;
    }}
    function linkSection(title, links) {{
      const details = el('details', {{}}, [el('summary', {{ text: `${{title}} (${{links.length}})` }})]);
      const list = el('div', {{ class: 'source-grid' }});
      for (const link of links) {{
        list.append(el('div', {{ class: 'source-item' }}, [el('a', {{ href: link.url, text: link.url }})]));
      }}
      if (!links.length) list.append(el('div', {{ class: 'section-text', text: 'No stored links for this bookmark.' }}));
      details.append(list);
      return details;
    }}
    function enrichmentSection(enrichments) {{
      const details = el('details', {{}}, [el('summary', {{ text: `Captured Context (${{enrichments.length}})` }})]);
      const list = el('div', {{ class: 'source-grid' }});
      for (const item of enrichments) {{
        list.append(el('div', {{ class: 'source-item' }}, [
          el('strong', {{ text: `${{item.source_type}}: ${{item.title || item.source_url}}` }}),
          el('div', {{}}, [el('a', {{ href: item.source_url, text: item.source_url }})]),
          el('div', {{ class: 'section-text', text: item.content_text || '' }}),
        ]));
      }}
      if (!enrichments.length) list.append(el('div', {{ class: 'section-text', text: 'Run enrich to capture full post, thread, and linked-page context.' }}));
      details.append(list);
      return details;
    }}
    function mediaSection(media) {{
      const details = el('details', {{}}, [el('summary', {{ text: `Visible Media Metadata (${{media.length}})` }})]);
      const list = el('div', {{ class: 'source-grid' }});
      for (const item of media) {{
        list.append(el('div', {{ class: 'source-item' }}, [
          el('strong', {{ text: item.alt || item.source_type || 'media' }}),
          el('div', {{}}, [el('a', {{ href: item.url, text: item.url }})]),
        ]));
      }}
      if (!media.length) list.append(el('div', {{ class: 'section-text', text: 'No visible media metadata was captured. TweetKB does not download or OCR images yet.' }}));
      details.append(list);
      return details;
    }}
    function entitySection(entities) {{
      const details = el('details', {{}}, [el('summary', {{ text: `Entities (${{entities.length}})` }})]);
      details.append(el('div', {{ class: 'chips' }}, entities.map(entity => el('span', {{ class: 'chip', text: `${{entity.name}} · ${{entity.type}}` }}))));
      return details;
    }}
    init();
  </script>
</body>
</html>
"""
