#!/usr/bin/env python3
"""
Git Commit & Push Tool for TwitterOrganizer

Usage:
    python tools/git_commit_push.py status
    python tools/git_commit_push.py log [--n=10]
    python tools/git_commit_push.py add <file> [<file>...]
    python tools/git_commit_push.py commit <message>
    python tools/git_commit_push.py push [--force]
    python tools/git_commit_push.py auto <type> <message> [--files <file>...]

Types: feat, fix, refactor, test, docs, ci, chore, perf

This tool:
- Shows git status --short
- Accepts explicit file paths only (no git add .)
- Creates conventional commits
- Verifies remote is https://github.com/AdityaVG13/TwitterOrganizer.git
- Pushes current branch
- Logs commits to docs/BUILD_LOG.md
"""

import subprocess
import sys
import json
from pathlib import Path
from datetime import datetime, timezone

REPO_ROOT = Path(__file__).parent.parent.resolve()
EXPECTED_REMOTE = "https://github.com/AdityaVG13/TwitterOrganizer.git"
BUILD_LOG = REPO_ROOT / "docs" / "BUILD_LOG.md"


def run_git(cmd: list[str], cwd: Path | None = None) -> dict:
    try:
        r = subprocess.run(
            ["git"] + cmd,
            capture_output=True,
            text=True,
            cwd=cwd or REPO_ROOT,
            timeout=30,
        )
        return {
            "ok": r.returncode == 0,
            "returncode": r.returncode,
            "stdout": r.stdout.strip(),
            "stderr": r.stderr.strip(),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def get_status() -> list[str]:
    r = run_git(["status", "--porcelain"])
    if not r["ok"]:
        return [f"[error] {r.get('stderr', 'failed')}"]
    files = [line for line in r["stdout"].split("\n") if line]
    return files


def get_branch() -> str:
    r = run_git(["branch", "--show-current"])
    return r.get("stdout", "unknown")


def get_remote() -> str:
    r = run_git(["remote", "get-url", "origin"])
    return r.get("stdout", "")


def get_log(n: int = 10) -> list[str]:
    r = run_git(["log", f"--oneline", f"-{n}"])
    if not r["ok"]:
        return []
    return [line for line in r["stdout"].split("\n") if line]


def add_files(files: list[str]) -> list[str]:
    """Add explicit files (rejects dot paths)."""
    errors = []
    added = []
    for f in files:
        if f in (".", "./", "*"):
            errors.append(f"[reject] Will not 'git add {f}' — use explicit paths")
            continue
        path = REPO_ROOT / f
        if not path.exists():
            errors.append(f"[reject] File not found: {f}")
        else:
            r = run_git(["add", f])
            if r["ok"]:
                added.append(f"[add] {f}")
            else:
                errors.append(f"[error] Failed to add {f}: {r.get('stderr', '')}")
    return added + errors


def commit(message: str, files: list[str] | None = None) -> dict:
    """Commit with explicit files or staged changes."""
    if files:
        # Add explicit files first
        result = add_files(files)
        if any("[reject]" in r or "[error]" in r for r in result):
            return {"ok": False, "messages": result}

    # Verify staged
    staged = get_status()
    if not staged:
        return {"ok": False, "messages": ["[error] Nothing staged to commit"]}

    r = run_git(["commit", "-m", message])
    if r["ok"]:
        # Log to BUILD_LOG
        _append_commit_log(message)
        return {"ok": True, "messages": [f"[commit] {message}"]}
    else:
        return {"ok": False, "messages": [f"[error] {r.get('stderr', 'commit failed')}"]}


def push(force: bool = False) -> dict:
    """Push to origin, verify remote URL first."""
    remote = get_remote()
    if remote != EXPECTED_REMOTE:
        return {
            "ok": False,
            "messages": [
                f"[error] Remote mismatch!",
                f"  Expected: {EXPECTED_REMOTE}",
                f"  Got:      {remote}",
                "Set remote with: git remote set-url origin <url>",
            ],
        }

    branch = get_branch()
    cmd = ["push", "--force"] if force else ["push"]
    r = run_git(cmd)

    if r["ok"]:
        return {"ok": True, "messages": [f"[push] {branch} -> origin/{branch}"]}
    else:
        err = r.get("stderr", "")
        if "authentication" in err.lower() or "credential" in err.lower():
            return {
                "ok": False,
                "messages": [
                    "[error] Authentication failed",
                    "Fix with: gh auth login",
                    f"  or: git push origin {branch}",
                ],
            }
        return {"ok": False, "messages": [f"[error] {err}"]}


def auto_commit(commit_type: str, message: str, files: list[str] | None = None) -> dict:
    """Create a conventional commit and push."""
    VALID_TYPES = {"feat", "fix", "refactor", "test", "docs", "ci", "chore", "perf"}
    if commit_type not in VALID_TYPES:
        return {
            "ok": False,
            "messages": [
                f"[error] Invalid type '{commit_type}'. Use one of: {', '.join(VALID_TYPES)}"
            ],
        }

    # Commit
    full_msg = f"{commit_type}: {message}"
    commit_result = commit(full_msg, files)
    if not commit_result["ok"]:
        return commit_result

    # Push
    push_result = push()
    return {
        "ok": commit_result["ok"] and push_result["ok"],
        "messages": commit_result["messages"] + push_result["messages"],
    }


def _append_commit_log(message: str) -> None:
    """Append commit to BUILD_LOG.md."""
    try:
        BUILD_LOG.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        branch = get_branch()
        entry = f"- `{timestamp}` [{branch}] {message}\n"
        with open(BUILD_LOG, "a") as f:
            f.write(entry)
    except Exception:
        pass  # Don't fail on logging errors


def main() -> None:
    args = sys.argv[1:]

    if not args or "--help" in args or "-h" in args:
        print(__doc__)
        sys.exit(0)

    cmd = args[0]

    if cmd == "status":
        branch = get_branch()
        print(f"Branch: {branch}")
        remote = get_remote()
        match = "✓" if remote == EXPECTED_REMOTE else "✗"
        print(f"Remote: {match} {remote}")
        print(f"Changes:")
        files = get_status()
        if files:
            for f in files:
                print(f"  {f}")
        else:
            print("  (clean)")
        sys.exit(0)

    elif cmd == "log":
        n = 10
        for a in args[1:]:
            if a.startswith("--n="):
                n = int(a.split("=", 1)[1])
        entries = get_log(n)
        for e in entries:
            print(e)
        sys.exit(0)

    elif cmd == "add":
        files = args[1:]
        if not files:
            print("[error] add requires file paths")
            sys.exit(1)
        results = add_files(files)
        for r in results:
            print(r)
        sys.exit(0)

    elif cmd == "commit":
        if len(args) < 2:
            print("[error] commit requires a message")
            sys.exit(1)
        files = None
        msg = args[1]
        if "--files" in args:
            idx = args.index("--files")
            files = args[idx + 1 : idx + 1 + args[idx + 1 :].index("--") if "--" in args[idx + 1 :] else len(args[idx + 1 :])]
            if "--" in args[idx + 1 :]:
                files = args[idx + 1 : args.index("--", idx)]
        result = commit(msg, files)
        for m in result["messages"]:
            print(m)
        sys.exit(0 if result["ok"] else 1)

    elif cmd == "push":
        force = "--force" in args
        result = push(force)
        for m in result["messages"]:
            print(m)
        sys.exit(0 if result["ok"] else 1)

    elif cmd == "auto":
        if len(args) < 3:
            print("[error] auto <type> <message> [--files <file>...]")
            sys.exit(1)
        commit_type = args[1]
        message = args[2]
        files = None
        if "--files" in args:
            idx = args.index("--files")
            files = args[idx + 1 :]
        result = auto_commit(commit_type, message, files)
        for m in result["messages"]:
            print(m)
        sys.exit(0 if result["ok"] else 1)

    else:
        print(f"Unknown command: {cmd}")
        print("Commands: status, log, add, commit, push, auto")
        sys.exit(1)


if __name__ == "__main__":
    main()
