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


def test_interactive_collect_defaults_to_apple_events():
    command = _interactive_command_for_choice(
        "3",
        input_fn=_answers(["", "y", "", ""]),
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


def test_interactive_analyze_export_builds_folder_command():
    command = _interactive_command_for_choice(
        "4a",
        input_fn=_answers(["all", "local-hash", "y", "ai-agents", "", "any", "", "50", "markdown", "./exports/notes", "n", "0.4"]),
    )

    assert command == [
        "analyze-export",
        "--stage",
        "all",
        "--provider",
        "local-hash",
        "--include-category",
        "ai-agents",
        "--limit",
        "50",
        "--adapter",
        "markdown",
        "--vault",
        "./exports/notes",
        "--min-confidence",
        "0.4",
    ]


def test_interactive_enrich_builds_conversation_command():
    command = _interactive_command_for_choice(
        "5",
        input_fn=_answers(["", "", "10", "1.5", "always", "20", "n", "n", "n"]),
    )

    assert command == [
        "enrich",
        "--apple-events",
        "--limit",
        "10",
        "--wait",
        "1.5",
        "--include-conversation",
        "always",
        "--max-conversation-items",
        "20",
    ]


def test_interactive_enrich_builds_media_command():
    command = _interactive_command_for_choice(
        "5",
        input_fn=_answers(["", "", "10", "1.5", "never", "n", "y", "metadata", "", "2", "y"]),
    )

    assert command == [
        "enrich",
        "--apple-events",
        "--limit",
        "10",
        "--wait",
        "1.5",
        "--include-conversation",
        "never",
        "--include-media",
        "--vision-provider",
        "metadata",
        "--max-media",
        "2",
        "--all",
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


def test_interactive_media_export_builds_bundle_command():
    command = _interactive_command_for_choice(
        "17",
        input_fn=_answers(["./exports/media-review", "25", "n"]),
    )

    assert command == ["media-export", "--out", "./exports/media-review", "--limit", "25"]
