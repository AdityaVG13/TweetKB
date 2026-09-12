from __future__ import annotations

import json

from tweetkb.cli import main
from tweetkb.db import Store


def test_bare_invocation_prints_usage_and_does_not_open_a_menu(capsys):
    code = main([])
    captured = capsys.readouterr()
    assert code == 0
    assert "tweetkb search" in captured.out
    assert "Select:" not in captured.out
    assert "no LLM" in captured.out


def test_capabilities_json_declares_offline_no_llm(capsys):
    code = main(["capabilities", "--json"])
    captured = capsys.readouterr()
    assert code == 0
    payload = json.loads(captured.out)
    assert payload["offline"] is True
    assert payload["llm_required"] is False
    assert payload["default_analyze_provider"] == "local-hash"
    names = {cmd["name"] for cmd in payload["commands"]}
    assert {"search", "collect", "analyze", "next"}.issubset(names)
    assert payload["database"]["env"] == "TWEETKB_DB"
    assert "tweetkb/bookmarks.sqlite3" in payload["database"]["default"]


def test_unknown_command_suggests_search(capsys):
    code = main(["serach", "rust"])
    captured = capsys.readouterr()
    assert code == 2
    assert "unknown command" in captured.err
    assert "tweetkb search rust" in captured.err
    assert captured.out == ""


def test_next_json_suggests_collect_when_empty(db_path, capsys):
    store = Store(db_path, create=True)
    store.init()
    store.close()

    code = main(["--db", str(db_path), "next", "--json"])
    captured = capsys.readouterr()
    assert code == 0
    payload = json.loads(captured.out)
    assert payload["total"] == 0
    assert payload["offline"] is True
    assert "tweetkb collect --all" in payload["suggested"]


def test_agent_guide_says_no_password_and_no_llm(capsys):
    code = main(["agent-guide"])
    captured = capsys.readouterr()
    assert code == 0
    text = captured.out.lower()
    assert "do not ask the user for an x password" in text
    assert "no llm" in text or "offline" in text
