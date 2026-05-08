# Changelog

## 0.5.0

- Added normal Chrome and Apple Events collection paths for logged-in X sessions.
- Added full X article capture during enrichment.
- Added optional tweet image analysis and media review bundle export.
- Added `--all` collection stopping when already-saved bookmark history is reached.
- Added per-stage analysis state so unchanged classify, entity, and embed work is skipped.
- Preserved visual bookmark order during collection and made enrichment print queued rows.
- Reordered the interactive menu to match the intended collect, enrich, analyze, export workflow.
- Improved Browser-Harness/CDP fallback behavior and Apple Events script escaping.

## 0.4.0

- Added question-aware thread/reply context enrichment for X conversations.
- Added interactive `spec` export and a menu path for analyze-and-export workflows.

## 0.3.0

- Renamed the public package metadata to `tweetkb`.
- Added `uv tool install` docs for direct `tweetkb` usage.
- Added Browser-Harness setup docs for public users.
- Added terminal menu screenshot and transcript docs.
- Added release notes for the `v0.3.0` GitHub release.
- Added interactive terminal menu and progress output for long-running workflows.
- Added selective analysis filters for categories, review states, and limits.
- Removed internal prompt docs and personal release helper from the tracked tree.
- Added public release audit command.
- Added license, security policy, contributing guide, release checklist, and config example.
- Hardened git ignores for runtime data, local config, exports, and release artifacts.
- Expanded config paths from `~` and environment variables.
- Added Ruff to the development checks.

## 0.2.0

- Added collection, analysis, graph, project mining, review, export, and compression workflows.
- Added SQLite migrations and tests for the core local-first pipeline.
