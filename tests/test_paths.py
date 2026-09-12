from __future__ import annotations

from pathlib import Path

from tweetkb.cli import main
from tweetkb.release_audit import Violation, audit_repository, format_violations, scan_paths


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
