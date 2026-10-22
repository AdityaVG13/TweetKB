from __future__ import annotations

import argparse
import fnmatch
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class Rule:
    name: str
    pattern: re.Pattern[str]
    message: str


@dataclass(frozen=True)
class Violation:
    path: str
    rule: str
    message: str
    line: int | None = None
    snippet: str = ""


TRACKED_PATH_DENYLIST = (
    "data/*",
    "obsidian-vault/*",
    "exports/*",
    "*.db",
    "*.sqlite",
    "*.sqlite3",
    "*.sqlite3-*",
    "*.db-*",
    "*.bak",
    "*.twz",
)

HISTORY_PATH_DENYLIST = (
    "docs/MINIMAX_MASTER_PROMPT.md",
    "docs/MINIMAX_MASTER_PROMPT_BACKUP.md",
    "docs/PROMPTS/*",
)

CONTENT_RULES: tuple[Rule, ...] = (
    Rule(
        "absolute-user-home-path",
        re.compile(r"(?i)(/Users/[A-Za-z0-9._-]+|/home/[A-Za-z0-9._-]+|C:\\Users\\[A-Za-z0-9._-]+)"),
        "absolute local user path found",
    ),
    Rule(
        "windows-user-profile-path",
        re.compile(r"(?i)\\Users\\[A-Za-z0-9._-]+"),
        "windows user profile path found",
    ),
    Rule(
        "secret-assignment",
        re.compile(
            r"(?i)\b(api[_-]?key|secret|token|password|bearer)\b\s*[:=]\s*['\"][^'\"\s]{12,}['\"]"
        ),
        "possible committed secret found",
    ),
)

RUNTIME_PATH_DENYLIST = TRACKED_PATH_DENYLIST + (
    "tweetkb.toml",
    "tweetkb.local.toml",
    ".env",
    ".env.*",
)

ALLOWED_TRACKED_PATHS = {"data/.gitkeep"}


def audit_repository(root: Path, strict_worktree: bool = False) -> list[Violation]:
    root = root.resolve()
    violations = scan_tracked_files(root)
    if strict_worktree:
        violations.extend(scan_ignored_runtime_files(root))
    return violations


def scan_tracked_files(root: Path) -> list[Violation]:
    files = _git_files(root)
    return scan_paths(root, files, denylist=TRACKED_PATH_DENYLIST)


def scan_paths(root: Path, files: Iterable[Path], denylist: Iterable[str]) -> list[Violation]:
    violations: list[Violation] = []
    root = root.resolve()
    for rel_path in files:
        rel = rel_path.as_posix()
        if rel in ALLOWED_TRACKED_PATHS:
            continue
        if _matches_any(rel, denylist):
            violations.append(
                Violation(
                    path=rel,
                    rule="tracked-runtime-artifact",
                    message="runtime data or generated artifact is tracked",
                )
            )
            continue

        abs_path = root / rel_path
        if not abs_path.is_file():
            continue
        data = abs_path.read_bytes()
        if _looks_binary(data):
            continue
        text = data.decode("utf-8", errors="replace")
        for line_no, line in enumerate(text.splitlines(), start=1):
            for rule in CONTENT_RULES:
                if rule.pattern.search(line):
                    violations.append(
                        Violation(
                            path=rel,
                            rule=rule.name,
                            message=rule.message,
                            line=line_no,
                            snippet=line.strip()[:160],
                        )
                    )
    return violations


def scan_ignored_runtime_files(root: Path) -> list[Violation]:
    ignored = _git_ignored_files(root)
    violations: list[Violation] = []
    for rel_path in ignored:
        rel = rel_path.as_posix()
        if _matches_any(rel, RUNTIME_PATH_DENYLIST):
            violations.append(
                Violation(
                    path=rel,
                    rule="ignored-runtime-artifact",
                    message="ignored runtime data exists in the working tree",
                )
            )
    return violations


def scan_history(root: Path) -> list[Violation]:
    """Flag private paths and secret-like text that remain in git history."""
    root = root.resolve()
    listed = subprocess.run(
        ["git", "rev-list", "--objects", "--all"],
        cwd=root,
        check=True,
        stdout=subprocess.PIPE,
    )
    blobs: list[tuple[str, str]] = []
    for line in listed.stdout.decode("utf-8", errors="replace").splitlines():
        if " " not in line:
            continue
        sha, path = line.split(" ", 1)
        blobs.append((sha, path))

    violations: list[Violation] = []
    seen: set[tuple[str, str, str]] = set()

    def add(path: str, rule: str, message: str, snippet: str = "", line: int | None = None) -> None:
        key = (path, rule, snippet)
        if key in seen:
            return
        seen.add(key)
        violations.append(Violation(path=path, rule=rule, message=message, line=line, snippet=snippet))

    flagged_paths: set[str] = set()
    for _sha, path in blobs:
        if path in flagged_paths or not _matches_any(path, HISTORY_PATH_DENYLIST):
            continue
        flagged_paths.add(path)
        add(path, "private-history-path", "private file remains in git history")

    if not blobs:
        return violations

    dumped = subprocess.run(
        ["git", "cat-file", "--batch"],
        cwd=root,
        input="".join(f"{sha}\n" for sha, _path in blobs).encode(),
        check=True,
        stdout=subprocess.PIPE,
    )
    data = dumped.stdout
    offset = 0
    for _sha, path in blobs:
        newline = data.find(b"\n", offset)
        if newline < 0:
            break
        header = data[offset:newline].decode("utf-8", errors="replace")
        offset = newline + 1
        parts = header.split()
        if len(parts) < 3:
            continue
        size = int(parts[2])
        blob = data[offset : offset + size]
        offset += size + 1
        if parts[1] != "blob" or _looks_binary(blob):
            continue
        text = blob.decode("utf-8", errors="replace")
        for line_no, line in enumerate(text.splitlines(), start=1):
            for rule in CONTENT_RULES:
                if rule.pattern.search(line):
                    add(path, rule.name, rule.message, line.strip()[:160], line_no)
    return violations


def format_violations(violations: Iterable[Violation]) -> str:
    rows = []
    for item in violations:
        location = item.path if item.line is None else f"{item.path}:{item.line}"
        suffix = f" | {item.snippet}" if item.snippet else ""
        rows.append(f"{location} [{item.rule}] {item.message}{suffix}")
    return "\n".join(rows)


def _git_files(root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=root,
        check=True,
        stdout=subprocess.PIPE,
    )
    return [Path(p) for p in result.stdout.decode().split("\0") if p]


def _git_ignored_files(root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "status", "--ignored", "--short", "-z"],
        cwd=root,
        check=True,
        stdout=subprocess.PIPE,
    )
    entries = result.stdout.decode().split("\0")
    ignored: list[Path] = []
    for entry in entries:
        if entry.startswith("!! "):
            ignored.append(Path(entry[3:]))
    return ignored


def _matches_any(path: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def _looks_binary(data: bytes) -> bool:
    return b"\0" in data[:4096]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scan this repository for public-release blockers.")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--strict-worktree", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    violations = audit_repository(args.root, strict_worktree=args.strict_worktree)
    if args.json:
        print(json.dumps([item.__dict__ for item in violations], indent=2))
    elif violations:
        print(format_violations(violations))
    else:
        print("release audit passed")
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
