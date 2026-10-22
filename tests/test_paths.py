from __future__ import annotations

import subprocess
from pathlib import Path

from tweetkb.cli import main
from tweetkb.release_audit import Violation, audit_repository, format_violations, scan_history, scan_paths


def test_compress_command_is_not_part_of_the_cli(capsys):
    try:
        code = main(["compress", "export", "--out", "x.twz"])
    except SystemExit as exc:
        code = int(exc.code or 1)
    captured = capsys.readouterr()
    assert code != 0
    combined = (captured.err + captured.out).lower()
    assert "invalid choice" in combined or "unrecognized" in combined or "unknown" in combined
    assert "tweetzip" not in combined


def test_help_lists_search_and_not_compress(capsys):
    try:
        code = main(["--help"])
    except SystemExit as exc:
        code = int(exc.code or 0)
    captured = capsys.readouterr()
    assert code == 0
    assert "search" in captured.out
    assert "compress" not in captured.out
    assert "TweetZip" not in captured.out


def test_tracked_tree_has_no_absolute_user_paths():
    violations = audit_repository(Path.cwd())
    assert violations == []


def test_source_and_docs_do_not_hardcode_developer_home_paths():
    blocked = ("~/Developer",)
    roots = [Path("src"), Path("docs"), Path("README.md"), Path("tweetkb.example.toml")]
    hits = []
    for root in roots:
        files = [root] if root.is_file() else root.rglob("*")
        for path in files:
            if not path.is_file():
                continue
            if path.suffix not in {".py", ".md", ".toml", ".txt", ""} and path.name != "README.md":
                continue
            text = path.read_text(errors="ignore")
            for token in blocked:
                if token in text:
                    hits.append(f"{path}: {token}")
    assert hits == []


def test_release_audit_flags_absolute_home_path(tmp_path):
    bad_file = tmp_path / "bad.txt"
    bad_file.write_text("path=" + "/Users/" + "localname/project\n")
    violations = scan_paths(tmp_path, [Path("bad.txt")], denylist=())
    assert [item.rule for item in violations] == ["absolute-user-home-path"]


def test_release_audit_flags_tracked_runtime_data(tmp_path):
    data_file = tmp_path / "data" / "bookmarks.sqlite3"
    data_file.parent.mkdir()
    data_file.write_text("not a real database")
    violations = scan_paths(tmp_path, [Path("data/bookmarks.sqlite3")], denylist=("data/*",))
    assert [item.rule for item in violations] == ["tracked-runtime-artifact"]


def test_history_scan_flags_a_removed_home_path(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "test")
    secret = repo / "docs" / "MINIMAX_MASTER_PROMPT.md"
    secret.parent.mkdir()
    secret.write_text("tools live at " + "/Users/" + "localname/AI/MiniMax/tools\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "add private prompt")
    secret.unlink()
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "remove private prompt")

    violations = scan_history(repo)
    rules = {item.rule for item in violations}
    assert "private-history-path" in rules
    assert "absolute-user-home-path" in rules


def test_public_docs_do_not_claim_the_tool_never_deletes():
    text = "\n".join(
        path.read_text()
        for path in (Path("README.md"), Path("docs/PRIVACY.md"))
    ).lower()
    assert "never posts, likes, follows, deletes" not in text
    assert "unbookmark" in text
    assert "--yes" in text


def test_terminal_demo_matches_the_current_wizard():
    text = Path("docs/TERMINAL_DEMO.md").read_text()
    assert "tweetkb-menu.png" not in text
    assert "TweetZip" not in text
    assert "1. Collect bookmarks" in text
    assert "tweetkb wizard" in text
    assert not Path("docs/assets/tweetkb-menu.png").exists()


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def test_format_violations_includes_location_and_rule():
    text = format_violations(
        [
            Violation(
                path="README.md",
                line=3,
                rule="example-rule",
                message="example message",
                snippet="bad line",
            )
        ]
    )
    assert "README.md:3 [example-rule] example message | bad line" in text
