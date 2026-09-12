from __future__ import annotations

import json

COMMANDS = [
    {
        "name": "search",
        "aliases": ["find", "query"],
        "read": True,
        "json": True,
        "usage": "tweetkb search QUERY [--from HANDLE] [--category SLUG] [--domain HOST] [--sort rank|saved|posted] [--json] [--open] [--limit N]",
        "notes": "Offline FTS5 search. Query may include from:handle, cat:slug, link:host, saved:7d.",
    },
    {
        "name": "collect",
        "read": False,
        "json": False,
        "usage": "tweetkb collect [--all] [--headless] [--limit N]",
        "notes": "Needs a logged-in Chrome session. Does not need an X password.",
    },
    {
        "name": "analyze",
        "read": False,
        "json": False,
        "usage": "tweetkb analyze [--stage classify|entities|embed|all]",
        "notes": "Default provider is local-hash. No LLM. No network.",
    },
    {
        "name": "stats",
        "read": True,
        "json": True,
        "usage": "tweetkb stats",
        "notes": "Always prints JSON.",
    },
    {
        "name": "digest",
        "read": True,
        "json": True,
        "usage": "tweetkb digest [--json] [--saved-after DATE]",
        "notes": "Categories, outbound domains, authors. Offline. No LLM.",
    },
    {
        "name": "related",
        "read": True,
        "json": True,
        "usage": "tweetkb related STATUS_ID [--kinds url,domain,author] [--json]",
        "notes": "Neighbors by exact URL, domain, or author. Category is opt-in. No embeddings.",
    },
    {
        "name": "map",
        "read": True,
        "json": True,
        "usage": "tweetkb map --from HANDLE [--json]",
        "notes": "ASCII geography for one author: domains and categories.",
    },
    {
        "name": "atlas",
        "read": True,
        "json": False,
        "usage": "tweetkb atlas [--out PATH] [--open]",
        "notes": "Write a static local HTML map. No server. No force-directed layout.",
    },
    {
        "name": "next",
        "read": True,
        "json": True,
        "usage": "tweetkb next [--json]",
        "notes": "One-shot triage: counts, top categories, copy-paste next commands.",
    },
    {
        "name": "capabilities",
        "read": True,
        "json": True,
        "usage": "tweetkb capabilities --json",
        "notes": "Machine-readable contract. Does not open the database.",
    },
    {
        "name": "agent-guide",
        "read": True,
        "json": False,
        "usage": "tweetkb agent-guide",
        "notes": "Paste-ready handbook for agents.",
    },
]

EXIT_CODES = {
    "0": "success, including empty search results",
    "1": "runtime error",
    "2": "usage or input error",
    "130": "interrupted",
}

USAGE = """tweetkb — local X bookmark knowledge base (offline, no LLM)

  tweetkb collect [--all] [--headless]
  tweetkb search QUERY [--from HANDLE] [--category SLUG] [--domain HOST] [--json] [--open]
  tweetkb digest [--json]
  tweetkb related STATUS_ID [--json]
  tweetkb map --from HANDLE
  tweetkb atlas
  tweetkb analyze [--stage classify|entities|embed|all]
  tweetkb stats
  tweetkb next --json
  tweetkb capabilities --json
  tweetkb agent-guide
  tweetkb tui
  tweetkb wizard

Search examples:
  tweetkb search rust
  tweetkb search 'from:karpathy gpu'
  tweetkb search mcp --category coding --json
  tweetkb search 'link:github.com'
  tweetkb search rust --sort saved
  tweetkb search rust saved:7d
  tweetkb digest --json

Analyze uses local keywords, entities, and hash embeddings. No API key.
Bare `tweetkb` prints this help. Use `tweetkb tui` for the interactive menu.
"""

AGENT_GUIDE = """# TweetKB agent guide

TweetKB is a local SQLite knowledge base of X bookmarks. It runs fully offline.
Do not ask the user for an X password. Do not upload the database.

## First commands

```
tweetkb capabilities --json
tweetkb next --json
tweetkb stats
tweetkb search QUERY --json --limit 20
```

If the database is missing, run `tweetkb init` then `tweetkb collect --all`.

## Search

- Tokens are AND.
- `from:handle` or `--from handle` filters author.
- `cat:slug` or `--category slug` filters primary classification.
- `link:host` or `--domain host` filters outbound URLs.
- `saved:7d` / `saved:2w` or `--saved-after DATE` filters bookmark time (`captured_at`), not tweet age.
- `--sort rank|saved|posted` (default rank).
- `--json` writes `{"hits":[...]}` to stdout. Progress and errors go to stderr.
- Empty results: exit 0, `{"hits":[]}` with `--json`.
- `--open [N]` opens the top N tweet URLs in the system browser.

## Analyze (no LLM)

```
tweetkb analyze --stage classify
tweetkb analyze --stage all
```

Default `--provider local-hash`. Do not switch to openai/ollama unless the user asks.

## Collect

Needs a logged-in Chrome. Prefer `tweetkb collect --all`.
On macOS this uses Apple Events against the running browser.
`--headless` copies the Chrome profile and uses a background Chrome.

Stop rule: skip a prefix of already-saved tweets; stop after `--stop-after-known`
already-saved tweets in a row at the older end (default 8).
`--no-stop-at-existing` rescans the whole timeline.

## Exit codes

0 success (including no search hits)
1 runtime error
2 usage / missing query / missing database
130 interrupted
"""

ALIASES = {
    "find": "search",
    "query": "search",
    "ls": "stats",
    "status": "stats",
    "triage": "next",
}

KNOWN_COMMANDS = [
    "init",
    "migrate",
    "collect",
    "enrich",
    "login",
    "chrome-debug",
    "analyze",
    "analyze-export",
    "classify",
    "entities",
    "embed",
    "cluster",
    "projects",
    "export",
    "review",
    "graph",
    "search",
    "find",
    "query",
    "doctor",
    "media-export",
    "release-audit",
    "benchmark",
    "compact",
    "stats",
    "digest",
    "related",
    "map",
    "atlas",
    "serve",
    "tui",
    "wizard",
    "capabilities",
    "agent-guide",
    "next",
    "unbookmark",
    "repair-links",
]


def capabilities() -> dict:
    return {
        "name": "tweetkb",
        "offline": True,
        "llm_required": False,
        "default_analyze_provider": "local-hash",
        "stdout": "data",
        "stderr": "diagnostics",
        "exit_codes": EXIT_CODES,
        "commands": COMMANDS,
    }


def capabilities_json() -> str:
    return json.dumps(capabilities(), indent=2, sort_keys=True) + "\n"


def next_payload(stats: dict) -> dict:
    total = int(stats.get("total") or 0)
    categories = stats.get("categories") or {}
    ranked = sorted(
        ((slug, int((info or {}).get("count") or 0)) for slug, info in categories.items()),
        key=lambda item: item[1],
        reverse=True,
    )
    top = [{"slug": slug, "count": count} for slug, count in ranked if count][:8]
    suggested = []
    if total == 0:
        suggested.append("tweetkb collect --all")
        suggested.append("tweetkb init")
    else:
        suggested.append("tweetkb search QUERY --json --limit 20")
        if top:
            suggested.append(f"tweetkb search --category {top[0]['slug']} --json --limit 20")
        suggested.append("tweetkb analyze --stage classify")
        suggested.append("tweetkb digest --json")
        suggested.append("tweetkb atlas")
        suggested.append("tweetkb stats")
    return {
        "offline": True,
        "llm_required": False,
        "total": total,
        "needs_review": int(stats.get("needs_review") or 0),
        "categories": top,
        "suggested": suggested,
    }


def closest_command(word: str) -> str | None:
    needle = (word or "").lower()
    if not needle or needle in KNOWN_COMMANDS or needle in ALIASES:
        return ALIASES.get(needle)
    best = None
    best_dist = 3
    for cmd in KNOWN_COMMANDS:
        dist = _levenshtein(needle, cmd)
        if dist < best_dist:
            best = cmd
            best_dist = dist
    return best


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        curr = [i]
        for j, cb in enumerate(b, start=1):
            curr.append(min(curr[j - 1] + 1, prev[j] + 1, prev[j - 1] + (ca != cb)))
        prev = curr
    return prev[-1]
