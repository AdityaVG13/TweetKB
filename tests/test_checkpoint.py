from tweetkb.checkpoint import Checkpoint


def test_checkpoint_add_seen(tmp_path):
    cp = Checkpoint(tmp_path / "checkpoint.json")
    cp.add_seen(["2", "1", "2"])
    data = cp.read()
    assert data["seen_status_ids"] == ["1", "2"]
    assert data["batches"] == 1

