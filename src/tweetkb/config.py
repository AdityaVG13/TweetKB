from __future__ import annotations

import os
from pathlib import Path
from typing import Any


DEFAULT_CONFIG_LOCATIONS = [
    Path("tweetkb.toml"),
    Path.home() / ".config" / "tweetkb" / "tweetkb.toml",
]


def load_config(config_path: Path | None = None) -> dict[str, Any]:
    """Load configuration from file and environment variables."""
    config: dict[str, Any] = {
        "database": {"path": "data/bookmarks.sqlite3"},
        "browser": {
            "app": "Google Chrome",
            "profile": str(Path.home() / "Library/Application Support/Google/Chrome"),
            "debug_port": 9222,
        },
        "collect": {
            "batch_size": 20,
            "wait": 1.5,
            "stagnant_batches": 10,
        },
        "analysis": {
            "default_provider": "local-hash",
            "changed_only": True,
        },
        "export": {
            "obsidian": {"exclude_categories": ["misc"], "exclude_review": False},
            "logseq": {"exclude_categories": ["misc"], "exclude_review": False},
        },
    }

    # Load from file
    if config_path and config_path.exists():
        config = _merge_config(config, _load_toml(config_path))
    else:
        for loc in DEFAULT_CONFIG_LOCATIONS:
            if loc.exists():
                config = _merge_config(config, _load_toml(loc))
                break

    # Override from environment
    if db_path := os.environ.get("TWEETKB_DB"):
        config["database"]["path"] = db_path
    if browser_app := os.environ.get("TWEETKB_BROWSER_APP"):
        config["browser"]["app"] = browser_app
    if browser_profile := os.environ.get("TWEETKB_BROWSER_PROFILE"):
        config["browser"]["profile"] = browser_profile
    if debug_port := os.environ.get("TWEETKB_BROWSER_DEBUG_PORT"):
        config["browser"]["debug_port"] = int(debug_port)
    if provider := os.environ.get("TWEETKB_ANALYSIS_PROVIDER"):
        config["analysis"]["default_provider"] = provider

    return config


def _merge_config(base: dict, override: dict) -> dict:
    """Deep merge override dict into base dict."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _merge_config(result[key], value)
        else:
            result[key] = value
    return result


def _load_toml(path: Path) -> dict:
    """Load a TOML file. Minimal parser for simple configs."""
    try:
        import tomllib
    except ImportError:
        try:
            import tomli as tomllib
        except ImportError:
            return _load_toml_fallback(path)
    with path.open("rb") as f:
        return tomllib.load(f)


def _load_toml_fallback(path: Path) -> dict:
    """Fallback TOML parser using basic string parsing."""
    result: dict = {}
    current_section: dict = {}
    section_name = ""

    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            if section_name:
                result[section_name] = current_section
            section_name = line[1:-1].strip()
            current_section = {}
        elif "=" in line:
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if value.isdigit():
                value = int(value)
            elif value in ("true", "false"):
                value = value == "true"
            current_section[key] = value

    if section_name:
        result[section_name] = current_section

    return result
