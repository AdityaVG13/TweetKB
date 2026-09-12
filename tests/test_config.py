from __future__ import annotations

from tweetkb.config import load_config, resolve_db_path


def test_config_expands_tilde_and_env_in_file_paths(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("TWEETKB_VAULT", str(tmp_path / "vault"))
    config_path = tmp_path / "tweetkb.toml"
    config_path.write_text(
        "\n".join(
            [
                "[database]",
                'path = "~/kb/bookmarks.sqlite3"',
                "[browser]",
                f'profile = "{tmp_path / "chrome"}"',
            ]
        )
        + "\n"
    )

    config = load_config(config_path)

    assert config["database"]["path"] == str(tmp_path / "kb" / "bookmarks.sqlite3")
    assert not config["database"]["path"].startswith("~")


def test_tweedkb_db_env_overrides_config_file(tmp_path, monkeypatch):
    monkeypatch.setenv("TWEETKB_DB", str(tmp_path / "from-env.sqlite3"))
    config_path = tmp_path / "tweetkb.toml"
    config_path.write_text("[database]\npath = \"ignored.sqlite3\"\n")

    config = load_config(config_path)

    assert config["database"]["path"] == str(tmp_path / "from-env.sqlite3")


def test_resolve_db_path_uses_xdg_when_cwd_has_no_database(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("TWEETKB_DB", raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    monkeypatch.setenv("HOME", str(tmp_path))

    path = resolve_db_path()

    assert path == (tmp_path / "xdg" / "tweetkb" / "bookmarks.sqlite3").resolve()


def test_resolve_db_path_prefers_existing_cwd_database(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("TWEETKB_DB", raising=False)
    local = tmp_path / "data" / "bookmarks.sqlite3"
    local.parent.mkdir()
    local.write_bytes(b"")

    path = resolve_db_path()

    assert path.resolve() == local.resolve()


def test_resolve_db_path_env_wins_over_cwd_database(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    local = tmp_path / "data" / "bookmarks.sqlite3"
    local.parent.mkdir()
    local.write_bytes(b"")
    env_db = tmp_path / "from-env.sqlite3"
    monkeypatch.setenv("TWEETKB_DB", str(env_db))

    path = resolve_db_path()

    assert path.resolve() == env_db.resolve()
