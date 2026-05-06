from tweetkb.cli import _interactive_command_for_choice


def _answers(values):
    iterator = iter(values)
    return lambda _prompt: next(iterator)


def test_interactive_collect_builds_apple_events_command():
    command = _interactive_command_for_choice(
        "3",
        input_fn=_answers(["apple-events", "y", "", ""]),
    )

    assert command == ["collect", "--apple-events", "--all", "--batch-size", "20", "--wait", "1.5"]


def test_interactive_analyze_builds_filtered_command():
    command = _interactive_command_for_choice(
        "4",
        input_fn=_answers(["entities", "n", "ai-agents,coding", "misc", "needs-review", "", "25"]),
    )

    assert command == [
        "analyze",
        "--stage",
        "entities",
        "--no-changed-only",
        "--include-category",
        "ai-agents,coding",
        "--exclude-category",
        "misc",
        "--needs-review",
        "--limit",
        "25",
    ]


def test_interactive_export_builds_obsidian_command():
    command = _interactive_command_for_choice(
        "6",
        input_fn=_answers(["obsidian", "", "ai-agents", "", "y", "0.5"]),
    )

    assert command == [
        "export",
        "--adapter",
        "obsidian",
        "--vault",
        "./obsidian-vault",
        "--include-category",
        "ai-agents",
        "--exclude-review",
        "--min-confidence",
        "0.5",
    ]
