# Security Policy

## Supported Versions

Security fixes target the latest release.

## Reporting A Vulnerability

Open a private security advisory on the hosting platform, or contact the
maintainers through the repository security channel.

Do not include live credentials, browser cookies, exported vaults, or bookmark
databases in reports. Provide a minimal reproduction with synthetic data.

## Security Notes

- Collection reads from a logged-in browser session.
- The tool does not need X/Twitter credentials in code or config.
- `tweetkb.toml`, `.env`, `data/`, `exports/`, and vault directories are ignored.
- Optional cloud LLM providers may receive bookmark text when explicitly enabled.
- Run `uv run tweetkb release-audit` before publishing source.
