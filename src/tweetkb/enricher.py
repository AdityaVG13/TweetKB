from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

BLOCKED_LINK_HOSTS = {
    "business.x.com",
    "x.com",
    "twitter.com",
    "mobile.twitter.com",
    "help.x.com",
    "ads.twitter.com",
    "analytics.twitter.com",
}

BLOCKED_LINK_TEXT = {
    "ads",
    "advertising",
    "analytics",
    "cookie",
    "cookies",
    "help",
    "privacy",
    "terms",
}


@dataclass
class EnrichResult:
    enriched: int = 0
    skipped: int = 0
    failed: int = 0


def enriched_text_for_analysis(store, bookmark_id: int, fallback_text: str) -> str:
    enrichments = store.get_content_enrichments(bookmark_id)
    if not enrichments:
        return fallback_text
    contents = [row["content_text"] for row in enrichments if row["content_text"]]
    if not contents:
        return fallback_text
    return "\n\n".join([fallback_text, *contents])


def enrich_with_apple_events(
    store,
    bookmarks: list[Any],
    browser_app: str = "Google Chrome",
    wait_seconds: float = 2.0,
    include_links: bool = False,
    max_links: int = 3,
) -> EnrichResult:
    result = EnrichResult()
    for row in bookmarks:
        bookmark_id = int(row["id"])
        status_url = row["status_url"]
        try:
            payload = capture_x_content_with_apple_events(status_url, browser_app, wait_seconds)
        except (RuntimeError, ValueError):
            result.failed += 1
            continue

        content = payload.get("content_text", "").strip()
        if not content:
            result.skipped += 1
            continue
        saved = store.set_content_enrichment(
            bookmark_id=bookmark_id,
            source_url=payload.get("url") or status_url,
            source_type=payload.get("source_type") or "x-status",
            title=payload.get("title") or "",
            content_text=content,
            metadata={
                "status_url": status_url,
                "article_clicked": payload.get("article_clicked", False),
                "content_length": len(content),
            },
        )
        if saved:
            result.enriched += 1
        else:
            result.skipped += 1

        if include_links:
            for link in _candidate_outbound_links(payload.get("outbound_links", []), max_links=max_links):
                try:
                    linked_payload = capture_page_content_with_apple_events(link, browser_app, wait_seconds)
                except (RuntimeError, ValueError):
                    result.failed += 1
                    continue
                linked_content = linked_payload.get("content_text", "").strip()
                if not linked_content:
                    result.skipped += 1
                    continue
                final_url = linked_payload.get("url") or link
                if _is_blocked_link(final_url):
                    result.skipped += 1
                    continue
                if store.set_content_enrichment(
                    bookmark_id=bookmark_id,
                    source_url=final_url,
                    source_type="linked-page",
                    title=linked_payload.get("title") or "",
                    content_text=linked_content,
                    metadata={
                        "status_url": status_url,
                        "requested_url": link,
                        "content_length": len(linked_content),
                    },
                ):
                    result.enriched += 1
                else:
                    result.skipped += 1
    return result


def _candidate_outbound_links(links: list[Any], max_links: int = 3) -> list[str]:
    candidates: list[str] = []
    for raw_link in links:
        link = raw_link.get("url", "") if isinstance(raw_link, dict) else str(raw_link or "")
        label = " ".join(
            [
                raw_link.get("text", "") if isinstance(raw_link, dict) else "",
                raw_link.get("aria", "") if isinstance(raw_link, dict) else "",
            ]
        ).lower()
        if _is_blocked_link(link):
            continue
        if any(token in label for token in BLOCKED_LINK_TEXT):
            continue
        parsed = urlparse(link)
        path = parsed.path.lower()
        if "/intent/" in path or "/share" in path or "/privacy" in path or "/terms" in path:
            continue
        if link not in candidates:
            candidates.append(link)
    return candidates[:max_links]


def _is_blocked_link(link: str) -> bool:
    if not link or not link.startswith(("http://", "https://")):
        return True
    parsed = urlparse(link)
    host = parsed.netloc.lower().removeprefix("www.")
    return host in BLOCKED_LINK_HOSTS


def capture_x_content_with_apple_events(
    status_url: str,
    browser_app: str = "Google Chrome",
    wait_seconds: float = 2.0,
) -> dict[str, Any]:
    click_js = r"""
(() => {
  const links = Array.from(document.querySelectorAll('a[href]'));
  const article = links.find(a => /\/i\/article\//.test(a.href));
  if (article) {
    article.click();
    return true;
  }
  return false;
})()
"""
    extract_js = r"""
(() => {
  const textOf = (node) => node ? (node.innerText || node.textContent || '').trim() : '';
  const unique = (items) => Array.from(new Set(items.map(x => (x || '').trim()).filter(Boolean)));
  const uniqueLinks = (items) => {
    const seen = new Set();
    return items.filter(item => {
      if (!item || !item.url || seen.has(item.url)) return false;
      seen.add(item.url);
      return true;
    });
  };
  const tweetTexts = unique(Array.from(document.querySelectorAll('[data-testid="tweetText"]')).map(textOf));
  const articleLike = [
    document.querySelector('[data-testid="article"]'),
    document.querySelector('article'),
    document.querySelector('main')
  ].map(textOf).find(t => t && t.length > 200) || '';
  const mainText = textOf(document.querySelector('main')) || textOf(document.body);
  const linkRoot = document.querySelector('[data-testid="article"]') || document.querySelector('article') || document.querySelector('main') || document.body;
  const links = Array.from(linkRoot.querySelectorAll('a[href]')).map(a => {
    try {
      return {
        url: new URL(a.getAttribute('href'), location.origin).href,
        text: (a.innerText || a.textContent || '').trim(),
        aria: (a.getAttribute('aria-label') || '').trim()
      };
    } catch (_) {
      return null;
    }
  }).filter(Boolean);
  const content = unique([...tweetTexts, articleLike, mainText])
    .join('\n\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
  return JSON.stringify({
    url: location.href,
    title: document.title || '',
    source_type: /\/i\/article\//.test(location.href) ? 'x-article' : 'x-status',
    content_text: content,
    tweet_texts: tweetTexts,
    outbound_links: uniqueLinks(links),
    content_length: content.length
  });
})()
"""
    script = f"""
    on run
      tell application {json.dumps(browser_app)}
        if not (exists front window) then error "No Chrome window is open"
        tell front window
          set active tab index to (count of tabs)
          set newTab to make new tab at end of tabs
          set active tab index to (count of tabs)
          set URL of active tab to {json.dumps(status_url)}
        end tell
        repeat 30 times
          delay 0.2
          tell active tab of front window
            set currentUrl to execute javascript "location.href"
          end tell
          if currentUrl contains {json.dumps(str(status_url).split("/status/")[-1])} then exit repeat
        end repeat
        delay {float(wait_seconds)}
        tell active tab of front window
          set currentUrl to execute javascript "location.href"
          if currentUrl does not contain {json.dumps(str(status_url).split("/status/")[-1])} then error "Chrome did not navigate to requested status URL"
          set clickedArticle to execute javascript {json.dumps(click_js)}
        end tell
        if clickedArticle is true then delay {float(wait_seconds)}
        tell active tab of front window
          set rawPayload to execute javascript {json.dumps(extract_js)}
        end tell
        close active tab of front window
      end tell
      return "TWEETKB_JSON=" & rawPayload
    end run
    """
    proc = subprocess.run(["osascript"], input=script, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip())
    for line in reversed(proc.stdout.splitlines()):
        if line.startswith("TWEETKB_JSON="):
            try:
                payload = json.loads(line.removeprefix("TWEETKB_JSON="))
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"Invalid JSON payload from Chrome: {line[-500:]}") from exc
            final_url = payload.get("url") or ""
            status_id = str(status_url).split("/status/")[-1].split("?")[0]
            if status_id not in final_url and "/i/article/" not in final_url:
                raise RuntimeError(f"Chrome ended on unexpected URL: {final_url}")
            return payload
    raise RuntimeError(f"No TWEETKB_JSON payload found: {proc.stdout[-1000:]}")


def capture_page_content_with_apple_events(
    url: str,
    browser_app: str = "Google Chrome",
    wait_seconds: float = 2.0,
) -> dict[str, Any]:
    extract_js = r"""
(() => {
  const textOf = (node) => node ? (node.innerText || node.textContent || '').trim() : '';
  const candidates = [
    document.querySelector('article'),
    document.querySelector('main'),
    document.querySelector('[role="main"]'),
    document.body
  ];
  const content = candidates.map(textOf).find(t => t && t.length > 500) || textOf(document.body);
  const metaDescription = document.querySelector('meta[name="description"]')?.content || '';
  return JSON.stringify({
    url: location.href,
    title: document.title || '',
    description: metaDescription,
    content_text: [document.title || '', metaDescription, content || '']
      .filter(Boolean)
      .join('\n\n')
      .replace(/\n{3,}/g, '\n\n')
      .trim(),
    content_length: (content || '').length
  });
})()
"""
    script = f"""
    on run
      tell application {json.dumps(browser_app)}
        if not (exists front window) then error "No Chrome window is open"
        tell front window
          set active tab index to (count of tabs)
          set newTab to make new tab at end of tabs
          set active tab index to (count of tabs)
          set URL of active tab to {json.dumps(url)}
        end tell
        delay {float(wait_seconds)}
        tell active tab of front window
          set rawPayload to execute javascript {json.dumps(extract_js)}
        end tell
        close active tab of front window
      end tell
      return "TWEETKB_JSON=" & rawPayload
    end run
    """
    proc = subprocess.run(["osascript"], input=script, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip())
    for line in reversed(proc.stdout.splitlines()):
        if line.startswith("TWEETKB_JSON="):
            try:
                return json.loads(line.removeprefix("TWEETKB_JSON="))
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"Invalid JSON payload from Chrome: {line[-500:]}") from exc
    raise RuntimeError(f"No TWEETKB_JSON payload found: {proc.stdout[-1000:]}")
