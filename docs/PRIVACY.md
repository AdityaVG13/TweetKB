# Privacy & Safety

## Data Storage

- **SQLite DB**: All bookmark text, metadata, and analysis stored locally at `data/bookmarks.sqlite3`
- **Checkpoint**: Collection state at `data/checkpoint.json`
- **Export vault**: Markdown notes at user-specified path
- **No cloud storage**: All data stays on your machine
- **No bundled personal data**: The public repository ships only `data/.gitkeep`, not a bookmark database or exported vault

## What's Collected

When you run `tweetkb collect`, the browser automation reads:

- Tweet text and raw DOM content
- Author name and handle
- Tweet timestamp
- All URLs in the tweet
- Status URL (bookmark link)

The collector does **not** collect:
- Your account credentials
- Your timeline, DMs, or follows
- Anything outside the bookmarks page

## Browser Automation

- Uses your **logged-in browser session** (Browser-Harness managed Chrome or your normal Chrome)
- Read-only: scrolls, reads DOM, extracts text
- Never posts, likes, follows, unfollows, deletes, messages, or changes account settings
- Never modifies your X/Twitter account

## Optional LLM Features

If you configure an LLM provider (OpenAI, Ollama):

- Tweet text may be sent to the provider API for classification/analysis
- Provider API keys stored in environment variables or config, not in code
- Disabled by default. You must opt in with `--provider openai` or `--provider ollama`
- Local Ollama sends data to localhost only

## What Leaves Your Machine

| Feature | Data Sent | Where |
|---------|-----------|-------|
| Collection | None (reads local browser) | N/A |
| Classification (local) | None | N/A |
| Classification (OpenAI) | Tweet text, categories | OpenAI API |
| Classification (Ollama) | Tweet text | localhost:11434 |
| Link enrichment | URL for title/description fetch | Target domain |

## Link Enrichment

`tweetkb enrich-links` fetches page titles and descriptions from URLs. This sends the URL to the target domain's server. It:

- Uses timeouts and respects rate limits
- Caches results in `links` table
- Never scrapes full page content aggressively
- Can be limited to specific domains

## Export Privacy

Exported vault files contain:
- Full tweet text
- Author info
- All extracted URLs
- Classification results

**Keep your vault private**. Vault exports are ignored by default.

## Secrets

- No API keys or secrets in code
- No credentials committed to git
- Config file (`tweetkb.toml`) should not contain secrets
- Use environment variables for sensitive config

## Browser Profile

Browser-Harness uses a separate Chrome profile at `~/.browser-harness/chrome-profiles/default`. It does not use your normal Chrome profile.

If using `--normal-chrome`, the collector uses your standard Chrome profile with remote debugging. This requires Chrome to be running with `--remote-debugging-port`.

## Security Recommendations

1. Keep your browser logged into X only in the Browser-Harness profile
2. Don't use `--normal-chrome` on a shared machine
3. Review `SECURITY.md` for reporting vulnerabilities
4. Keep `data/` directory out of git
5. Don't commit vault exports to git

## X/Twitter Terms

Using browser automation to access X may conflict with their Terms of Service. This tool is for personal use with your own bookmarks. Use responsibly.
