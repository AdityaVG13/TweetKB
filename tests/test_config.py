from tweetkb.config import load_config


def test_load_config_returns_dict():
    """load_config returns a dict with expected keys."""
    cfg = load_config()
    assert isinstance(cfg, dict)
    assert "database" in cfg
    assert "analysis" in cfg
