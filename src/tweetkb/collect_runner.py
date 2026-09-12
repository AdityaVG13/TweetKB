from __future__ import annotations

import json

RATE_LIMIT_MARKERS = (
    "looks like it might be automated",
    "you are rate limited",
    "sorry, you are rate limited",
    "rate limit exceeded",
)

RUNNER_JS = r"""
(() => {
  if (window.__tweetkbRunner && window.__tweetkbRunner.running) return 'already';
  const state = {running: true, seen: {}, order: [], rateLimited: false};
  const harvest = () => {
    const textOf = (node) => node ? (node.innerText || node.textContent || '').trim() : '';
    const abs = (href) => { try { return new URL(href, location.origin).href; } catch (_) { return href || ''; } };
    Array.from(document.querySelectorAll('article')).forEach((article) => {
      const links = Array.from(article.querySelectorAll('a[href]')).map(a => abs(a.getAttribute('href'))).filter(Boolean);
      const statusUrl = links.find(h => /\/status\/\d+/.test(h)) || '';
      const statusMatch = statusUrl.match(/\/status\/(\d+)/);
      const userName = article.querySelector('[data-testid="User-Name"]');
      const userText = textOf(userName);
      const handleMatch = userText.match(/@([A-Za-z0-9_]+)/);
      const tweetText = Array.from(article.querySelectorAll('[data-testid="tweetText"]')).map(textOf).filter(Boolean).join('\n\n');
      const time = article.querySelector('time');
      const item = {
        status_url: statusUrl,
        status_id: statusMatch ? statusMatch[1] : '',
        author_name: userText.split('\n')[0] || '',
        author_handle: handleMatch ? handleMatch[1] : '',
        tweet_text: tweetText,
        raw_text: '',
        created_at: time ? (time.getAttribute('datetime') || '') : '',
        links: Array.from(new Set(links)).filter(h => !h.includes('/analytics'))
      };
      if (item.status_id && item.tweet_text && !state.seen[item.status_id]) {
        state.order.push(item.status_id);
        state.seen[item.status_id] = item;
      }
    });
  };
  const tick = () => {
    if (!state.running) return;
    const wall = (document.body && document.body.innerText || '').toLowerCase();
    if (wall.includes('looks like it might be automated') || wall.includes('you are rate limited') || wall.includes('rate limit exceeded')) {
      state.rateLimited = true;
      state.running = false;
      return;
    }
    harvest();
    const articles = document.querySelectorAll('article');
    const last = articles[articles.length - 1];
    if (last) last.scrollIntoView({block: 'end', inline: 'nearest'});
    const col = document.querySelector('[data-testid="primaryColumn"]') || document.scrollingElement;
    if (col && col !== last) col.scrollBy(0, 1400);
    const n = state.order.length;
    const burstPause = n > 0 && n % 80 === 0 ? (4000 + Math.random() * 4000) : 0;
    setTimeout(tick, 900 + Math.random() * 900 + burstPause);
  };
  window.__tweetkbRunner = state;
  window.__tweetkbCursor = 0;
  tick();
  return 'started';
})()
"""

SNAPSHOT_JS = r"""
(() => {
  const s = window.__tweetkbRunner;
  if (!s) return JSON.stringify({ok: false, reason: 'no-runner', items: []});
  const start = window.__tweetkbCursor || 0;
  const ids = s.order.slice(start, start + 80);
  window.__tweetkbCursor = start + ids.length;
  return JSON.stringify({
    ok: true,
    rate_limited: !!s.rateLimited,
    running: !!s.running,
    total: s.order.length,
    items: ids.map((id) => s.seen[id]).filter(Boolean)
  });
})()
"""

STOP_JS = r"""
(() => {
  if (window.__tweetkbRunner) window.__tweetkbRunner.running = false;
  return 'stopped';
})()
"""


def detect_rate_limit(text: str) -> bool:
    lower = (text or "").lower()
    return any(marker in lower for marker in RATE_LIMIT_MARKERS)


def parse_snapshot(raw: str) -> dict:
    try:
        payload = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {"ok": False, "items": [], "rate_limited": detect_rate_limit(raw or "")}
    if not isinstance(payload, dict):
        return {"ok": False, "items": [], "rate_limited": False}
    items = payload.get("items") or []
    if not isinstance(items, list):
        items = []
    return {
        "ok": bool(payload.get("ok")),
        "items": items,
        "rate_limited": bool(payload.get("rate_limited")) or detect_rate_limit(raw or ""),
        "running": bool(payload.get("running")),
        "total": int(payload.get("total") or 0),
        "reason": str(payload.get("reason") or ""),
    }


def poll_seconds(*, added: int, empty_polls: int) -> float:
    if added == 0 and empty_polls == 0:
        return 5.0
    if added >= 15:
        return 8.0
    if added > 0:
        return 10.0
    return 12.0 + min(int(empty_polls), 3) * 4.0
