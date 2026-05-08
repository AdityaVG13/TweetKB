from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .classifier import classify_text
from .embeddings import embed_text
from .enricher import enriched_text_for_analysis
from .entities import extract_entities
from .util import stable_hash

ANALYSIS_STAGES = ("classify", "entities", "embed")


def _stage_provider(stage: str, provider: str) -> str:
    return provider if stage == "embed" else ""


def _embedding_current(store, bookmark_id: int, provider: str, analysis_hash: str) -> bool:
    row = store.conn.execute(
        "SELECT content_hash FROM embeddings WHERE bookmark_id = ? AND provider = ? ORDER BY updated_at DESC LIMIT 1",
        (bookmark_id, provider),
    ).fetchone()
    return bool(row and row["content_hash"] == analysis_hash)


def _stage_current(store, bookmark_id: int, stage: str, provider: str, analysis_hash: str) -> bool:
    stage_provider = _stage_provider(stage, provider)
    if store.analysis_state_current(bookmark_id, stage, stage_provider, analysis_hash):
        return True
    return stage == "embed" and _embedding_current(store, bookmark_id, provider, analysis_hash)


def analyze_bookmark(
    store,
    bookmark_row,
    provider: str = "local-hash",
    changed_only: bool = True,
) -> dict[str, Any]:
    """Analyze a single bookmark: classify, extract entities, embed."""
    bookmark_id = int(bookmark_row["id"])
    text = "\n".join([bookmark_row["tweet_text"] or "", bookmark_row["raw_text"] or ""])
    text = enriched_text_for_analysis(store, bookmark_id, text)
    analysis_hash = stable_hash(text)

    # Get links from DB
    links_rows = store.get_bookmark_links(bookmark_id)
    links = [r["url"] for r in links_rows]

    # Classify
    result = classify_text(text, links)
    primary = result["primary"]
    categories = result["categories"]
    confidence = result["confidence"]

    # Extract entities
    entity_tuples = extract_entities(text, links)
    entity_names = [e[0] for e in entity_tuples]

    # Embed
    vector, embed_provider, embed_model = embed_text(text, provider=provider)

    # Update DB: classifications
    store.set_classifications(bookmark_id, categories, primary, confidence)
    store.set_analysis_state(bookmark_id, "classify", "", analysis_hash)

    # Update DB: entities
    for name, etype, source in entity_tuples:
        entity_id = store.upsert_entity(name, etype, source)
        if entity_id:
            store.add_bookmark_entity(bookmark_id, entity_id, salience=0.5, evidence=text[:200])
    store.set_analysis_state(bookmark_id, "entities", "", analysis_hash)

    # Update DB: embedding
    store.set_embedding(bookmark_id, vector, embed_provider, embed_model, analysis_hash)
    store.set_analysis_state(bookmark_id, "embed", embed_provider, analysis_hash)

    # Update DB: summary/analysis
    store.update_bookmark_analysis(
        bookmark_id,
        summary=result.get("summary", ""),
        why_it_matters=result.get("why_it_matters", ""),
        needs_review=result.get("needs_review", True),
    )

    # Add tags
    store.add_tags(bookmark_id, result.get("tags", []))

    return {
        "bookmark_id": bookmark_id,
        "primary": primary,
        "categories": categories,
        "confidence": confidence,
        "entities": entity_names,
        "embedding_provider": embed_provider,
    }


def run_analysis(
    store,
    stage: str = "all",
    provider: str = "local-hash",
    changed_only: bool = True,
    include_categories: set[str] | None = None,
    exclude_categories: set[str] | None = None,
    needs_review: bool | None = None,
    review_state: str | None = None,
    limit: int | None = None,
    progress: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Run analysis pipeline on bookmarks."""
    stages = list(ANALYSIS_STAGES) if stage == "all" else [stage]
    if any(item not in ANALYSIS_STAGES for item in stages):
        raise ValueError(f"Unknown analysis stage: {stage}")

    total = 0
    classified = 0
    entities_added = 0
    embedded = 0

    bookmarks = store.list_bookmarks_for_analysis(
        changed_only=False,
        include_categories=include_categories,
        exclude_categories=exclude_categories,
        needs_review=needs_review,
        review_state=review_state,
        limit=limit,
    )
    selected = len(bookmarks)
    if progress:
        progress(f"analysis: selected={selected} stage={stage} provider={provider}")

    for index, row in enumerate(bookmarks, start=1):
        bookmark_id = int(row["id"])
        status_id = row["status_id"]
        text = "\n".join([row["tweet_text"] or "", row["raw_text"] or ""])
        text = enriched_text_for_analysis(store, bookmark_id, text)
        analysis_hash = stable_hash(text)
        active_stages = stages
        if changed_only:
            active_stages = [
                item for item in stages if not _stage_current(store, bookmark_id, item, provider, analysis_hash)
            ]
            if not active_stages:
                if progress:
                    progress(f"analysis: {index}/{selected} skipped unchanged {status_id}")
                continue
        total += 1
        if progress:
            progress(f"analysis: {index}/{selected} processing {status_id}")

        if "classify" in active_stages:
            links_rows = store.get_bookmark_links(bookmark_id)
            links = [r["url"] for r in links_rows]
            result = classify_text(text, links)
            primary = result["primary"]
            categories = result["categories"]
            confidence = result["confidence"]

            store.set_classifications(bookmark_id, categories, primary, confidence)
            store.update_bookmark_analysis(
                bookmark_id,
                summary=result.get("summary", ""),
                why_it_matters=result.get("why_it_matters", ""),
                needs_review=result.get("needs_review", True),
            )
            store.add_tags(bookmark_id, result.get("tags", []))
            store.set_analysis_state(bookmark_id, "classify", "", analysis_hash)
            classified += 1

        if "entities" in active_stages:
            links_rows = store.get_bookmark_links(bookmark_id)
            links = [r["url"] for r in links_rows]
            entity_tuples = extract_entities(text, links)
            for name, etype, source in entity_tuples:
                entity_id = store.upsert_entity(name, etype, source)
                if entity_id:
                    store.add_bookmark_entity(bookmark_id, entity_id, salience=0.5, evidence=text[:200])
            store.set_analysis_state(bookmark_id, "entities", "", analysis_hash)
            entities_added += len(entity_tuples)

        if "embed" in active_stages:
            vector, embed_provider, embed_model = embed_text(text, provider=provider)
            store.set_embedding(bookmark_id, vector, embed_provider, embed_model, analysis_hash)
            store.set_analysis_state(bookmark_id, "embed", embed_provider, analysis_hash)
            embedded += 1

    return {
        "total": total,
        "selected": selected,
        "classified": classified,
        "entities_added": entities_added,
        "embedded": embedded,
        "provider": provider,
    }
