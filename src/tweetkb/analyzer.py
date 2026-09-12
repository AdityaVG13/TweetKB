from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .enricher import enriched_text_for_analysis
from .pipeline import analysis_key, analyze_document

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


def _persist_analysis(store, bookmark_id: int, analysis, stages: list[str], text: str) -> dict[str, int]:
    classified = entities_added = embedded = 0
    if "classify" in stages:
        store.set_classifications(
            bookmark_id,
            list(analysis.categories),
            analysis.primary,
            analysis.confidence,
        )
        store.update_bookmark_analysis(
            bookmark_id,
            summary=analysis.summary,
            why_it_matters=analysis.why_it_matters,
            needs_review=analysis.needs_review,
        )
        store.set_tags(bookmark_id, list(analysis.tags))
        store.set_analysis_state(bookmark_id, "classify", "", analysis.analysis_hash)
        classified = 1
    if "entities" in stages:
        for name, etype, source in analysis.entities:
            entity_id = store.upsert_entity(name, etype, source)
            if entity_id:
                store.add_bookmark_entity(bookmark_id, entity_id, salience=0.5, evidence=text[:200])
        store.set_analysis_state(bookmark_id, "entities", "", analysis.analysis_hash)
        entities_added = len(analysis.entities)
    if "embed" in stages:
        store.set_embedding(
            bookmark_id,
            list(analysis.vector),
            analysis.embed_provider,
            analysis.embed_model,
            analysis.analysis_hash,
        )
        store.set_analysis_state(bookmark_id, "embed", analysis.embed_provider, analysis.analysis_hash)
        embedded = 1
    return {"classified": classified, "entities_added": entities_added, "embedded": embedded}


def analyze_bookmark(
    store,
    bookmark_row,
    provider: str = "local-hash",
    changed_only: bool = True,
) -> dict[str, Any]:
    bookmark_id = int(bookmark_row["id"])
    text = bookmark_row["tweet_text"] or ""
    text = enriched_text_for_analysis(store, bookmark_id, text)
    links = [r["url"] for r in store.get_bookmark_links(bookmark_id)]
    analysis = analyze_document(text, links, provider=provider)
    _persist_analysis(store, bookmark_id, analysis, list(ANALYSIS_STAGES), text)
    return {
        "bookmark_id": bookmark_id,
        "primary": analysis.primary,
        "categories": list(analysis.categories),
        "confidence": analysis.confidence,
        "entities": [name for name, _, _ in analysis.entities],
        "embedding_provider": analysis.embed_provider,
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
    stages = list(ANALYSIS_STAGES) if stage == "all" else [stage]
    if any(item not in ANALYSIS_STAGES for item in stages):
        raise ValueError(f"Unknown analysis stage: {stage}")

    total = classified = entities_added = embedded = 0
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

    bookmark_ids = [int(row["id"]) for row in bookmarks]
    links_by_id = store.link_urls_for_ids(bookmark_ids)
    enrichments_by_id = store.enrichment_texts_for_ids(bookmark_ids)

    with store.transaction():
        for index, row in enumerate(bookmarks, start=1):
            bookmark_id = int(row["id"])
            status_id = row["status_id"]
            text = row["tweet_text"] or ""
            extra = enrichments_by_id.get(bookmark_id) or []
            if extra:
                text = "\n\n".join([text, *extra])
            links = links_by_id.get(bookmark_id) or []
            analysis_hash = analysis_key(text, links)
            active_stages: list[str] = list(stages)
            if changed_only:
                active_stages = [
                    item for item in stages if not _stage_current(store, bookmark_id, item, provider, analysis_hash)
                ]
                if not active_stages:
                    if progress and (index == 1 or index == selected or index % 100 == 0):
                        progress(f"analysis: {index}/{selected} skipped unchanged")
                    continue
            total += 1
            if progress and (index == 1 or index == selected or index % 100 == 0):
                progress(f"analysis: {index}/{selected} processing {status_id}")
            analysis = analyze_document(text, links, provider=provider)
            counts = _persist_analysis(store, bookmark_id, analysis, active_stages, text)
            classified += counts["classified"]
            entities_added += counts["entities_added"]
            embedded += counts["embedded"]

    return {
        "total": total,
        "selected": selected,
        "classified": classified,
        "entities_added": entities_added,
        "embedded": embedded,
        "provider": provider,
    }
