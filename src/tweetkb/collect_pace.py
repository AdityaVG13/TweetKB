from __future__ import annotations

import random


def sleep_seconds(
    base: float,
    batch: int,
    *,
    all_bookmarks: bool,
    rng=None,
) -> float:
    """Human-ish pauses. A 0.7s metronome for --all looks like automation to X."""
    rng = rng or random
    if all_bookmarks:
        wait = max(float(base), 2.5) + rng.uniform(0.4, 1.8)
        if batch > 0 and batch % 30 == 0:
            wait += rng.uniform(15, 35)
        return wait
    return float(base) + rng.uniform(0, 0.35)
