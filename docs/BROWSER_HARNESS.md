# Browser-Harness Setup

TweetKB collects bookmarks by reading your logged-in browser. It does not ask for
your X/Twitter password, browser cookies, or API tokens.

The default collector expects `browser-harness` on `PATH`.

## Install

```bash
git clone https://github.com/browser-use/browser-harness ~/Developer/browser-harness
cd ~/Developer/browser-harness
uv tool install -e .
browser-harness --setup
browser-harness --doctor
```

If `browser-harness` is not found after install, refresh your shell:

```bash
uv tool update-shell
exec "$SHELL" -l
```

Then verify:

```bash
command -v browser-harness
browser-harness --version
browser-harness --doctor
```

## Recommended Flow

Install TweetKB as a tool:

```bash
uv tool install git+https://github.com/AdityaVG13/TweetKB.git
uv tool update-shell
```

Open a new terminal, then run:

```bash
tweetkb init
tweetkb login
tweetkb collect --limit 100 --batch-size 20
```

From a source checkout, prefix commands with `uv run`:

```bash
uv run tweetkb init
uv run tweetkb login
uv run tweetkb collect --limit 100 --batch-size 20
```

## Browser Modes

Default managed profile:

```bash
tweetkb login
tweetkb collect --limit 100
```

Browser-Harness keeps its managed Chrome profile under
`~/.browser-harness/chrome-profiles/default`. Log in to X/Twitter once there and
the session remains for later collection runs.

Normal Chrome profile:

```bash
tweetkb chrome-debug
tweetkb collect --normal-chrome --existing-tab --limit 100
```

Use this when you want TweetKB to read from your already logged-in Chrome
profile. Chrome may ask you to allow remote debugging once.

macOS Apple Events fallback:

```bash
tweetkb collect --apple-events --limit 100 --batch-size 10 --wait 1
```

Use this if Browser-Harness cannot attach. Chrome must allow JavaScript from
Apple Events.

## Troubleshooting

Run:

```bash
tweetkb doctor
browser-harness --doctor
```

Common fixes:

- `browser-harness not on PATH`: run `uv tool update-shell`, then restart the shell.
- Login page opens: log in to X/Twitter in the opened Chrome profile, then rerun collection.
- Empty collection: open `https://x.com/i/bookmarks` in the same profile and confirm bookmarks are visible.
- Chrome asks about remote debugging: click allow, then rerun the command.
- Normal Chrome attach is flaky: use the default managed profile instead.
- Apple Events fails on macOS: allow Chrome automation in System Settings.

## Privacy

TweetKB only stores collected data in your local SQLite database. By default that
database lives in `data/bookmarks.sqlite3`, and `data/` is ignored by git except
for `data/.gitkeep`.

The public repository and GitHub source archives do not include a bookmark
database.
