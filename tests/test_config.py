from tweetkb.config import load_config


def test_load_config_returns_dict():
    """load_config returns a dict with expected keys."""
    cfg = load_config()
    assert isinstance(cfg, dict)
    assert "database" in cfg
    assert "analysis" in cfg


def test_config_expands_user_and_env_paths(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    config_path = tmp_path / "tweetkb.toml"
    config_path.write_text(
        "\n".join(
            [
                "[database]",
                'path = "~/tweetkb/bookmarks.sqlite3"',
                "[browser]",
                'profile = "$HOME/chrome-profile"',
            ]
        )
    )

    monkeypatch.setenv("HOME", str(home))

    cfg = load_config(config_path)

    assert cfg["database"]["path"] == str(home / "tweetkb" / "bookmarks.sqlite3")
    assert cfg["browser"]["profile"] == str(home / "chrome-profile")


def test_environment_paths_are_expanded(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("TWEETKB_DB", "$HOME/db.sqlite3")

    cfg = load_config()

    assert cfg["database"]["path"] == str(home / "db.sqlite3")
