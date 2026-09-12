from __future__ import annotations

from conftest import add_bookmark

from tweetkb.analyzer import run_analysis
from tweetkb.cli import main


def test_classify_stage_does_not_write_embeddings(store):
    add_bookmark(store, "1", "New browser agent automation workflow with MCP tool use")

    result = run_analysis(store, stage="classify", changed_only=False)

    assert result["classified"] == 1
    assert result["embedded"] == 0
    row = store.conn.execute("SELECT count(*) AS n FROM embeddings").fetchone()
    assert int(row["n"]) == 0
    primary = store.conn.execute(
        "SELECT category_slug FROM classifications WHERE is_primary = 1"
    ).fetchone()
    assert primary["category_slug"] == "ai-agents"


def test_changed_only_skips_completed_classify_stage(store):
    add_bookmark(store, "1", "New browser agent automation workflow with MCP tool use")
    first = run_analysis(store, stage="classify", changed_only=True)
    second = run_analysis(store, stage="classify", changed_only=True)

    assert first["classified"] == 1
    assert second["classified"] == 0
    assert second["selected"] == 1


def test_analysis_limit_processes_only_n_rows(store):
    add_bookmark(store, "1", "agent mcp tool use")
    add_bookmark(store, "2", "rust compiler diagnostics")
    add_bookmark(store, "3", "obsidian vault sync")

    result = run_analysis(store, stage="classify", changed_only=False, limit=2)

    assert result["selected"] == 2
    assert result["classified"] == 2


def test_unknown_analysis_stage_hard_fails(store):
    add_bookmark(store, "1", "hello")
    try:
        run_analysis(store, stage="summarize")
    except ValueError as exc:
        assert "stage" in str(exc).lower()
    else:
        raise AssertionError("unknown analysis stage must hard-fail")


def test_analyze_all_persists_after_deferred_transaction(store):
    add_bookmark(store, "1", "New browser agent automation workflow with MCP tool use")
    add_bookmark(store, "2", "debugging a rust compiler borrow checker error in cargo test")

    result = run_analysis(store, stage="all", changed_only=False)

    assert result["classified"] == 2
    assert result["embedded"] == 2
    n = store.conn.execute("SELECT count(*) AS n FROM classifications WHERE is_primary = 1").fetchone()
    assert int(n["n"]) == 2
    n = store.conn.execute("SELECT count(*) AS n FROM embeddings").fetchone()
    assert int(n["n"]) == 2


def test_changed_only_reclassifies_when_outbound_links_are_added(store):
    bookmark_id = add_bookmark(store, "1", "I bookmarked this for later")
    first = run_analysis(store, stage="classify", changed_only=True)
    store._store_bookmark_links(bookmark_id, ("https://github.com/foo/bar",))
    second = run_analysis(store, stage="classify", changed_only=True)

    assert first["classified"] == 1
    assert second["classified"] == 1
    primary = store.conn.execute(
        "SELECT category_slug FROM classifications WHERE is_primary = 1 AND bookmark_id = ?",
        (bookmark_id,),
    ).fetchone()
    assert primary["category_slug"] == "coding"


def test_unmatched_tweet_still_gets_misc_as_primary(store):
    add_bookmark(store, "1", "This would have been so easy today")

    run_analysis(store, stage="classify", changed_only=False)

    row = store.conn.execute(
        "SELECT category_slug FROM classifications WHERE is_primary = 1"
    ).fetchone()
    assert row is not None
    assert row["category_slug"] == "misc"


def test_classify_does_not_keep_https_or_x_as_tags(store):
    bookmark_id = add_bookmark(store, "1", "see https://example.com/path later")
    store.add_tags(bookmark_id, ["https", "x"])

    run_analysis(store, stage="classify", changed_only=False)

    tags = set(store.get_bookmark_tags(bookmark_id))
    assert "https" not in tags
    assert "x" not in tags


def test_analyze_cli_missing_database_does_not_create_one(tmp_path, capsys):
    missing = tmp_path / "missing.sqlite3"

    code = main(["--db", str(missing), "analyze", "--stage", "classify"])

    captured = capsys.readouterr()
    assert code != 0
    assert not missing.exists()
    assert "tweetkb init" in (captured.err + captured.out).lower()
