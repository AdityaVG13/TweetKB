from __future__ import annotations

from dataclasses import dataclass

from .search import search_bookmarks


@dataclass(frozen=True)
class UnbookmarkCandidate:
    status_id: str
    status_url: str
    author_handle: str
    snippet: str


def list_unbookmark_candidates(store, query: str, limit: int = 50) -> list[UnbookmarkCandidate]:
    hits = search_bookmarks(store, query, limit=limit)
    out: list[UnbookmarkCandidate] = []
    for hit in hits:
        row = store.get_bookmark_by_status(hit.status_id)
        if row and row["review_state"] == "unbookmarked":
            continue
        out.append(
            UnbookmarkCandidate(
                status_id=hit.status_id,
                status_url=hit.status_url,
                author_handle=hit.author_handle,
                snippet=hit.snippet or hit.tweet_text,
            )
        )
    return out


def mark_unbookmarked(store, status_id: str) -> None:
    row = store.get_bookmark_by_status(status_id)
    if not row:
        raise ValueError(f"bookmark not found: {status_id}\nTry: tweetkb search {status_id}")
    store.review_bookmark(int(row["id"]), "unbookmarked")


def click_script(status_id: str) -> str:
    return f"""
(() => {{
  const id = {status_id!r};
  const articles = Array.from(document.querySelectorAll('article'));
  const article = articles.find((node) =>
    Array.from(node.querySelectorAll('a[href]')).some((a) => (a.getAttribute('href') || '').includes('/status/' + id))
  );
  if (!article) return JSON.stringify({{ok: false, reason: 'not-visible'}});
  const btn = article.querySelector('[data-testid="removeBookmark"], [data-testid="bookmark"]');
  if (!btn) return JSON.stringify({{ok: false, reason: 'no-button'}});
  const label = (btn.getAttribute('aria-label') || '').toLowerCase();
  const testid = btn.getAttribute('data-testid') || '';
  if (testid === 'removeBookmark' || label.includes('remove') || label.includes('bookmarked')) {{
    btn.click();
    return JSON.stringify({{ok: true, status_id: id}});
  }}
  return JSON.stringify({{ok: false, reason: 'not-bookmarked'}});
}})()
"""


def unbookmark_on_x(status_id: str, *, browser_app: str = "Google Chrome") -> dict:
    import json

    from .chrome_session import ChromeSessionError, ensure_bookmarks_tab, eval_js

    tab = ensure_bookmarks_tab(browser_app)
    raw = eval_js(browser_app, tab, click_script(status_id))
    try:
        payload = json.loads(raw or "{}")
    except json.JSONDecodeError as exc:
        raise ChromeSessionError(f"unbookmark JS did not return JSON: {raw!r}") from exc
    if not isinstance(payload, dict):
        raise ChromeSessionError(f"unbookmark JS returned {payload!r}")
    return payload
