from pathlib import Path

from tweetkb.release_audit import Violation, audit_repository, format_violations, scan_paths


def test_release_audit_current_tracked_tree_is_clean():
    violations = audit_repository(Path.cwd())

    assert violations == []


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
