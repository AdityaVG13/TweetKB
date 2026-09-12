from __future__ import annotations

from tweetkb.config import load_config


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
