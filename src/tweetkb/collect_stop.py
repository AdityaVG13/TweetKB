from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StopDecision:
    stop: bool
    reason: str


def leading_known_count(ordered_ids: list[str], known_ids: set[str]) -> int:
    count = 0
    for status_id in ordered_ids:
        if status_id in known_ids:
            count += 1
        else:
            break
    return count


def trailing_known_streak(ordered_ids: list[str], known_ids: set[str]) -> int:
    """How many already-saved IDs sit at the older end of the timeline."""
    body = ordered_ids[leading_known_count(ordered_ids, known_ids) :]
    streak = 0
    for status_id in reversed(body):
        if status_id in known_ids:
            streak += 1
        else:
            break
    return streak


def decide_scroll_stop(
    ordered_ids: list[str],
    known_ids: set[str],
    *,
    empty_scrolls: int,
    empty_scroll_limit: int = 10,
    known_streak: int = 8,
    limit: int | None = None,
    stop_at_existing: bool = True,
) -> StopDecision:
    """Incremental collect must survive re-bookmarking an old tweet.

    Bookmark time is not tweet time, so date windows are wrong. Same status
    bookmarked twice is one row. Stop only when the *older* end of the
    timeline is a run of already-saved IDs. A prefix of known IDs is recent
    re-bookmarks and must be skipped.
    """
    if limit is not None and len(ordered_ids) >= limit:
        return StopDecision(True, "limit")
    if empty_scrolls >= empty_scroll_limit:
        return StopDecision(True, "end_of_feed")
    if not stop_at_existing or not known_ids:
        return StopDecision(False, "continue")
    if trailing_known_streak(ordered_ids, known_ids) >= known_streak:
        return StopDecision(True, "known_streak")
    return StopDecision(False, "continue")


def merge_batch(
    order: list[str],
    items: dict[str, dict],
    batch: list[dict],
) -> tuple[list[str], dict[str, dict], int]:
    """Keep tweets after X virtualizes them out of the DOM."""
    added = 0
    for item in batch:
        status_id = str(item.get("status_id") or "")
        if not status_id or not (item.get("tweet_text") or "").strip():
            continue
        if status_id not in items:
            order.append(status_id)
            added += 1
        items[status_id] = item
    return order, items, added
