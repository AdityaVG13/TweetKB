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


_LOCAL_USER = "ad" + "itya"
_LOCAL_GITHUB = "ad" + "itya" + "vg13"
_LOCAL_AUTHOR = "ad" + "ityag"

CONTENT_RULES: tuple[Rule, ...] = (
    Rule(
        "absolute-user-home-path",
        re.compile(r"(?i)(/Users/[A-Za-z0-9._-]+|/home/[A-Za-z0-9._-]+|C:\\Users\\[A-Za-z0-9._-]+)"),
        "absolute local user path found",
    ),
    Rule(
        "local-user-identifier",
        re.compile(rf"(?i)\b({_LOCAL_USER}|{_LOCAL_AUTHOR}|{_LOCAL_GITHUB})\b"),
        "local developer identifier found",
    ),
    Rule(
        "private-repo-remote",
        re.compile(rf"(?i)github\.com[:/]{_LOCAL_GITHUB}/"),
        "personal repository remote found",
    ),
    Rule(
        "secret-assignment",
        re.compile(
            r"(?i)\b(api[_-]?key|secret|token|password|bearer)\b\s*[:=]\s*['\"][^'\"\s]{12,}['\"]"
        ),
        "possible committed secret found",
    ),
)

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
