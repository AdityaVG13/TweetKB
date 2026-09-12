from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .classifier import classify_text
from .embeddings import embed_text
from .entities import extract_entities
from .util import stable_hash


@dataclass(frozen=True)
class Analysis:
    primary: str
    categories: tuple[dict, ...]
    confidence: float
    tags: tuple[str, ...]
    entities: tuple[tuple[str, str, str], ...]
    needs_review: bool
    summary: str
    why_it_matters: str
    vector: tuple[float, ...]
    embed_provider: str
    embed_model: str
    analysis_hash: str


def analysis_key(text: str, links: Sequence[str] = ()) -> str:
    return stable_hash("\n".join([text, *sorted(links)]))


def analyze_document(
    text: str,
    links: Sequence[str] = (),
    provider: str = "local-hash",
) -> Analysis:
    """Pure analysis. No database, no network, no LLM."""
    frozen_links = tuple(links)
    classification = classify_text(text, frozen_links)
    entities = tuple(extract_entities(text, frozen_links))
    vector, embed_provider, embed_model = embed_text(text, provider=provider)
    return Analysis(
        primary=classification["primary"],
        categories=tuple(classification["categories"]),
        confidence=float(classification["confidence"]),
        tags=tuple(classification.get("tags") or ()),
        entities=entities,
        needs_review=bool(classification.get("needs_review", True)),
        summary=classification.get("summary") or "",
        why_it_matters=classification.get("why_it_matters") or "",
        vector=tuple(vector),
        embed_provider=embed_provider,
        embed_model=embed_model,
        analysis_hash=analysis_key(text, frozen_links),
    )
