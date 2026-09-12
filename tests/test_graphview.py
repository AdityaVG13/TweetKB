from __future__ import annotations

from tweetkb.graphview import ascii_flowchart, mermaid_flowchart
from tweetkb.relations import RelatedHit


def _hit(status_id: str, handle: str, text: str, kind: str, via: str) -> RelatedHit:
    return RelatedHit(
        bookmark_id=int(status_id),
        status_id=status_id,
        status_url=f"https://x.com/{handle}/status/{status_id}",
        author_handle=handle,
        tweet_text=text,
        category="coding",
        kind=kind,
        via=via,
    )


def test_mermaid_flowchart_is_lr_and_labels_the_url_edge():
    source = mermaid_flowchart(
        center_id="11",
        center_label="@alice CUDA Rust",
        hits=[_hit("22", "bob", "same repo notes", "same_url", "https://github.com/foo/bar")],
    )

    assert source.startswith("flowchart LR")
    assert "s11" in source
    assert "s22" in source
    assert "same_url" in source
    assert "github.com/foo/bar" in source


def test_ascii_flowchart_draws_the_center_and_a_neighbor():
    art = ascii_flowchart(
        center_id="11",
        center_label="@alice CUDA Rust",
        hits=[_hit("22", "bob", "same repo notes", "same_url", "https://github.com/foo/bar")],
    )

    assert "@alice" in art
    assert "@bob" in art or "bob" in art
    assert "same_url" in art
    assert "─" in art or "|" in art


def test_sonar_scope_draws_a_center_and_rotates_heading():
    from tweetkb.graphview import sonar_scope

    first = sonar_scope(tick=0, center_label="@alice", contacts=[("@bob", "same_url")])
    second = sonar_scope(tick=9, center_label="@alice", contacts=[("@bob", "same_url")])
    assert "◈" in first
    assert "RNG" in first
    assert first != second
