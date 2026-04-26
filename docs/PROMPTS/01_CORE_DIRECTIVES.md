# Core Directives & Operating Protocol

## Environment Note
Important MiniMax environment note: you have your own tool suite available under `/Users/Aditya/AI/MiniMax/tools` (also reachable on this Mac as `/Users/aditya/AI/MiniMax/tools`; Windows-style reference: `\Users\Aditya\AI\MiniMax\tools`). Inspect and use those tools before claiming something cannot be done.

## Full Autonomous Mode
Do not get stuck because a tool is missing. If you need a small helper, generator, migration runner, benchmark harness, fixture builder, schema inspector, graph exporter, compression tester, or validation script, build that tool inside the repo and keep going. If a third-party binary is missing, first look for an existing local equivalent, then implement a minimal replacement, then degrade gracefully with a documented fallback. Choose sensible defaults. Keep working through the full framework overnight. Leave a progress log and final report.

## Impossible-Mode Product Challenge
Build beyond a normal bookmark exporter. Treat this as the first version of a personal intelligence engine for builders. Create the thing that feels like it should not be possible from bookmarks alone: a local system that reads messy saved tweets, finds latent themes, extracts tools and ideas, builds a graph, proposes projects, writes research briefs, compresses its own corpus, exports to multiple knowledge tools, and leaves a reviewable audit trail. Do not merely satisfy the checklist. Use the checklist as the floor. Find leverage.

## GitHub Target
This project repository is `https://github.com/AdityaVG13/TwitterOrganizer`. Do not create or push to a different repository.

## Autonomous Operating Protocol

### Do:
- inspect before asking
- search before inventing
- use the MiniMax tools folder before declaring a blocker
- build small missing tools when they unblock the main work
- choose conservative defaults
- keep existing commands working
- run tests repeatedly
- write docs as you go
- leave the repo in a runnable state
- preserve user data
- prefer additive migrations over destructive changes
- log major decisions in `docs/BUILD_LOG.md`
- create `docs/MINIMAX_FINAL_REPORT.md` at the end

### Do Not:
- stop because a helper script does not exist
- stop because a fixture does not exist
- stop because an optional dependency is missing
- stop because a command needs a small wrapper
- stop because a schema inspector is needed
- stop because a benchmark harness is needed
- stop because an export verifier is needed
- stop because you need synthetic data
- stop because Zig is not installed
- stop because live X/Twitter is unavailable
- ask the user to make product decisions that can be handled with clear defaults

### When Blocked:
1. Inspect local files and docs.
2. Inspect `/Users/Aditya/AI/MiniMax/tools`.
3. Search the repo.
4. Build a minimal helper if it is small.
5. Add a fallback path.
6. Mark limitation in `docs/BUILD_LOG.md`.
7. Continue with the next valuable task.

## Completion Standard
Do not stop after implementing one or two isolated pieces. Continue until the whole backend framework is substantially built, hardened, tested, documented, and ready for review.

### Pass Framework:
- Pass 1: inspect and plan in BUILD_LOG
- Pass 2: schema and migrations
- Pass 3: analysis pipeline
- Pass 4: entities, graph, clusters, projects
- Pass 5: export adapters
- Pass 6: custom TweetZip compression
- Pass 7: review API and UI improvements
- Pass 8: tests and fixtures
- Pass 9: docs and CI
- Pass 10: performance, hardening, cleanup
- Pass 11: final verification and report

## Hardening Requirements
After initial implementation, harden the code:
- all CLI commands have useful `--help`
- errors are actionable
- no tracebacks for expected user mistakes
- live collection commands are clearly marked
- tests do not need live browser
- tests do not need live X/Twitter
- tests do not need API keys
- no generated DB or vault output in git
- no user-specific paths in tracked files
- no secrets
- migrations are additive and safe
- export overwrite behavior is documented
- compression verifier exists
- corrupt compressed archives fail cleanly
- provider config is optional
- LLM calls are disabled by default
- missing Zig gives clean fallback
- missing Browser-Harness gives clean message
- missing Apple Events permission gives clean message
