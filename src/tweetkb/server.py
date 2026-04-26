from __future__ import annotations

import html
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .categories import CATEGORY_LABELS
from .db import Store


class ReviewServer:
    def __init__(self, db_path: Path):
        self.db_path = db_path

    def handler(self):
        db_path = self.db_path

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                parsed = urlparse(self.path)
                if parsed.path == "/api/bookmarks":
                    self._json(self._bookmarks(parsed.query))
                    return
                self._html(index_html())

            def do_POST(self):
                parsed = urlparse(self.path)
                if parsed.path.startswith("/api/bookmarks/"):
                    bookmark_id = int(parsed.path.split("/")[3])
                    length = int(self.headers.get("content-length", "0"))
                    data = json.loads(self.rfile.read(length) or b"{}")
                    store = Store(db_path)
                    row = store.get_bookmark(bookmark_id)
                    if not row:
                        store.close()
                        self._json({"error": "not found"}, status=404)
                        return
                    store.conn.execute(
                        "UPDATE bookmarks SET needs_review=?, review_note=?, category=?, updated_at=datetime('now') WHERE id=?",
                        (
                            1 if data.get("needs_review") else 0,
                            data.get("review_note", row["review_note"]),
                            data.get("category", row["category"]),
                            bookmark_id,
                        ),
                    )
                    store.conn.commit()
                    store.close()
                    self._json({"ok": True})
                    return
                self._json({"error": "not found"}, status=404)

            def _bookmarks(self, query: str):
                args = parse_qs(query)
                category = args.get("category", [""])[0] or None
                q = args.get("q", [""])[0] or None
                review_arg = args.get("review", [""])[0]
                review = True if review_arg == "1" else False if review_arg == "0" else None
                store = Store(db_path)
                rows = [dict(row) for row in store.list_bookmarks(category=category, needs_review=review, q=q)]
                stats = store.stats()
                store.close()
                for row in rows:
                    row["links"] = json.loads(row.pop("links_json") or "[]")
                    row["use_cases"] = json.loads(row.pop("use_cases_json") or "[]")
                    row["entities"] = json.loads(row.pop("entities_json") or "[]")
                return {"bookmarks": rows, "stats": stats, "categories": CATEGORY_LABELS}

            def _json(self, payload, status: int = 200):
                body = json.dumps(payload).encode("utf-8")
                self.send_response(status)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _html(self, body: str):
                encoded = body.encode("utf-8")
                self.send_response(200)
                self.send_header("content-type", "text/html; charset=utf-8")
                self.send_header("content-length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

            def log_message(self, format, *args):
                return

        return Handler

    def serve(self, host: str = "127.0.0.1", port: int = 8765) -> None:
        httpd = ThreadingHTTPServer((host, port), self.handler())
        print(f"tweetkb review UI: http://{host}:{port}")
        httpd.serve_forever()


def index_html() -> str:
    categories = "".join(f'<option value="{html.escape(k)}">{html.escape(v)}</option>' for k, v in CATEGORY_LABELS.items())
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Twitter Bookmark KB</title>
<style>
body {{ margin:0; font:14px system-ui, -apple-system, BlinkMacSystemFont, sans-serif; background:#f6f7f8; color:#16181c; }}
header {{ display:flex; gap:10px; align-items:center; padding:14px 18px; background:#fff; border-bottom:1px solid #d8dde3; position:sticky; top:0; }}
h1 {{ font-size:18px; margin:0 18px 0 0; }}
input, select, button, textarea {{ font:inherit; border:1px solid #ccd2d9; border-radius:6px; padding:7px 9px; background:#fff; }}
button {{ cursor:pointer; }}
main {{ display:grid; grid-template-columns: 320px 1fr; min-height:calc(100vh - 58px); }}
#list {{ border-right:1px solid #d8dde3; background:#fff; overflow:auto; }}
.item {{ padding:12px 14px; border-bottom:1px solid #edf0f2; cursor:pointer; }}
.item:hover, .item.active {{ background:#edf6ff; }}
.item strong {{ display:block; margin-bottom:4px; }}
.meta {{ color:#536471; font-size:12px; }}
#detail {{ padding:22px; max-width:980px; }}
.panel {{ background:#fff; border:1px solid #d8dde3; border-radius:8px; padding:18px; }}
.row {{ display:flex; gap:10px; flex-wrap:wrap; margin:10px 0; }}
.pill {{ background:#eef1f4; border-radius:999px; padding:3px 8px; font-size:12px; }}
textarea {{ width:100%; min-height:90px; box-sizing:border-box; }}
pre {{ white-space:pre-wrap; line-height:1.45; }}
a {{ color:#0f62fe; }}
</style>
</head>
<body>
<header>
<h1>Bookmark KB</h1>
<input id="q" placeholder="Search">
<select id="category"><option value="">All categories</option>{categories}</select>
<select id="review"><option value="">All</option><option value="1">Needs review</option><option value="0">Reviewed</option></select>
<button onclick="load()">Search</button>
<span id="stats" class="meta"></span>
</header>
<main>
<section id="list"></section>
<section id="detail"><div class="panel">Select a bookmark.</div></section>
</main>
<script>
let rows = [];
let selected = null;
async function load() {{
  const p = new URLSearchParams();
  if (q.value) p.set('q', q.value);
  if (category.value) p.set('category', category.value);
  if (review.value) p.set('review', review.value);
  const res = await fetch('/api/bookmarks?' + p.toString());
  const data = await res.json();
  rows = data.bookmarks;
  stats.textContent = `${{data.stats.total}} total, ${{data.stats.needs_review}} need review`;
  list.innerHTML = rows.map(r => `<div class="item" onclick="show(${{r.id}})" id="row-${{r.id}}"><strong>${{escapeHtml(r.summary || r.tweet_text.slice(0,90))}}</strong><div class="meta">@${{escapeHtml(r.author_handle || '')}} · ${{escapeHtml(r.category)}} · ${{Math.round(r.confidence*100)}}%</div></div>`).join('');
}}
function show(id) {{
  selected = rows.find(r => r.id === id);
  document.querySelectorAll('.item').forEach(e => e.classList.remove('active'));
  const el = document.getElementById('row-' + id); if (el) el.classList.add('active');
  detail.innerHTML = `<div class="panel">
    <h2>${{escapeHtml(selected.summary || selected.status_id)}}</h2>
    <div class="row"><span class="pill">${{escapeHtml(selected.category)}}</span><span class="pill">${{selected.needs_review ? 'needs review' : 'reviewed'}}</span><span class="pill">${{Math.round(selected.confidence*100)}}%</span></div>
    <p><a href="${{selected.status_url}}" target="_blank">Open source tweet</a></p>
    <h3>Why It Matters</h3><p>${{escapeHtml(selected.why_it_matters)}}</p>
    <h3>Tweet Text</h3><pre>${{escapeHtml(selected.tweet_text || selected.raw_text)}}</pre>
    <h3>Use Cases</h3><ul>${{selected.use_cases.map(x => `<li>${{escapeHtml(x)}}</li>`).join('')}}</ul>
    <h3>Entities</h3><div class="row">${{selected.entities.map(x => `<span class="pill">${{escapeHtml(x)}}</span>`).join('')}}</div>
    <h3>Review Note</h3><textarea id="note">${{escapeHtml(selected.review_note || '')}}</textarea>
    <div class="row"><button onclick="save(false)">Mark reviewed</button><button onclick="save(true)">Keep in review</button></div>
  </div>`;
}}
async function save(needsReview) {{
  await fetch('/api/bookmarks/' + selected.id, {{method:'POST', headers:{{'content-type':'application/json'}}, body:JSON.stringify({{needs_review: needsReview, review_note: note.value}})}});
  await load();
  show(selected.id);
}}
function escapeHtml(s) {{ return String(s || '').replace(/[&<>"']/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c])); }}
q.addEventListener('keydown', e => {{ if(e.key === 'Enter') load(); }});
load();
</script>
</body>
</html>"""
