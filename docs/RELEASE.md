# Public Release Checklist

Use this checklist before publishing source, wheels, archives, or binaries.

## Source Hygiene

```bash
uv run tweetkb release-audit
git status --short --ignored
```

Expected tracked state:

- No `data/` files except `data/.gitkeep`
- No exported vaults
- No `.env` or local config
- No absolute user home paths
- No private local repository remotes in tracked files
- No committed API keys, tokens, passwords, cookies, or bearer strings

If you plan to zip the working directory instead of using `git archive`, run:

```bash
uv run tweetkb release-audit --strict-worktree
```

Strict mode fails when ignored runtime data exists locally. That is intentional.
For public downloads, prefer a clean clone or a source archive built from tracked
files only.

## History Hygiene

The tracked tree can be clean while git history still contains old author
metadata or removed files. For an anonymous public release, publish from a fresh
repository or an orphan branch created from the sanitized tree.

Do not publish an existing private history if the goal is no developer linkage.

## Build

```bash
uv sync --extra dev
uv run pytest
uv run ruff check .
uv run python -m compileall src tests tools
uv build
```

## Install Smoke Test

For a source checkout:

```bash
uv run tweetkb --help
printf '0\n' | uv run tweetkb
```

For a public tool install:

```bash
uv tool install --force git+https://github.com/AdityaVG13/TweetKB.git
tweetkb --help
printf '0\n' | tweetkb
```

## Malware Scans

Run local ClamAV:

```bash
clamscan -r --infected --bell .
clamscan dist/*
```

Run VirusTotal only for artifacts that are safe to upload. VirusTotal submissions
may be shared with security vendors.

```bash
uv run python tools/virustotal_upload.py dist/*
```

The VirusTotal upload helper is intentionally not bundled because API key setup
varies. If using the official `vt` CLI, configure `VT_API_KEY` outside the repo
and upload the built source distribution and wheel.

## Publish

Recommended source archive:

```bash
git archive --format=zip --output=tweetkb-source.zip HEAD
```

Recommended public repository flow:

```bash
mkdir ../tweetkb-public
git archive HEAD | tar -x -C ../tweetkb-public
cd ../tweetkb-public
git init
git add README.md pyproject.toml src tests docs tools CHANGELOG.md CONTRIBUTING.md LICENSE SECURITY.md tweetkb.example.toml data/.gitkeep
git commit -m "feat: public release"
```

Set the public remote only after reviewing `git log`, `git status --ignored`,
and release scan results.

## GitHub Release

```bash
git push origin main
git tag -a v0.3.0 -m "TweetKB v0.3.0"
git push origin v0.3.0
gh release create v0.3.0 --title "TweetKB v0.3.0" --notes-file docs/RELEASE_NOTES_v0.3.0.md
```
