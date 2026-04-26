from __future__ import annotations

from enum import Enum


class ReviewState(str, Enum):
    NEW = "new"
    NEEDS_REVIEW = "needs-review"
    APPROVED = "approved"
    EXCLUDED = "excluded"
    ARCHIVED = "archived"
    PROJECT_CANDIDATE = "project-candidate"


REVIEW_ACTIONS = {
    "approve": ReviewState.APPROVED,
    "exclude": ReviewState.EXCLUDED,
    "archive": ReviewState.ARCHIVED,
    "mark-project": ReviewState.PROJECT_CANDIDATE,
    "unmark": ReviewState.NEEDS_REVIEW,
}


def apply_review_action(store, bookmark_id: int, action: str, note: str = "") -> bool:
    """Apply a review action to a bookmark. Returns True if action was valid."""
    if action not in REVIEW_ACTIONS:
        return False
    state = REVIEW_ACTIONS[action].value
    store.review_bookmark(bookmark_id, state, note)
    return True


def list_review_queue(store, filters: dict | None = None) -> list:
    """List bookmarks in review queue based on filters."""
    filters = filters or {}
    review_state = filters.get("review_state")
    category = filters.get("category")
    q = filters.get("q")

    needs_review = store.list_bookmarks(
        needs_review=True,
        review_state=review_state,
        category=category,
        q=q,
    )
    return needs_review
