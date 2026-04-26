from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Bookmark:
    id: int | None = None
    status_id: str = ""
    status_url: str = ""
    author_id: int | None = None
    author_name: str = ""
    author_handle: str = ""
    tweet_text: str = ""
    raw_text: str = ""
    created_at: str = ""
    captured_at: str = ""
    updated_at: str = ""
    content_hash: str = ""
    collection_source: str = "browser"
    collection_run_id: str | None = None
    is_archived: bool = False
    is_deleted: bool = False
    is_exportable: bool = True
    needs_review: bool = True
    review_note: str = ""
    review_state: str = "new"
    summary: str = ""
    why_it_matters: str = ""


@dataclass
class Author:
    id: int | None = None
    handle: str = ""
    display_name: str = ""
    profile_url: str = ""
    first_seen_at: str = ""
    last_seen_at: str = ""
    bookmark_count: int = 0


@dataclass
class Link:
    id: int | None = None
    url: str = ""
    normalized_url: str = ""
    domain: str = ""
    title: str = ""
    description: str = ""
    content_type: str = ""
    first_seen_at: str = ""
    last_seen_at: str = ""


@dataclass
class Category:
    id: int | None = None
    slug: str = ""
    label: str = ""
    description: str = ""
    export_default: bool = True
    review_default: bool = False


@dataclass
class Classification:
    id: int | None = None
    bookmark_id: int = 0
    category_slug: str = ""
    confidence: float = 0.0
    method: str = ""
    rationale: str = ""
    is_primary: bool = False
    created_at: str = ""


@dataclass
class Entity:
    id: int | None = None
    name: str = ""
    normalized_name: str = ""
    type: str = "other"
    source: str = ""


@dataclass
class BookmarkEntity:
    bookmark_id: int = 0
    entity_id: int = 0
    salience: float = 0.5
    evidence: str = ""


@dataclass
class Tag:
    id: int | None = None
    name: str = ""


@dataclass
class Embedding:
    id: int | None = None
    bookmark_id: int = 0
    provider: str = "local-hash"
    model: str = "hash-v1"
    dims: int = 64
    vector: list[float] = field(default_factory=list)
    content_hash: str = ""
    updated_at: str = ""


@dataclass
class Cluster:
    id: int | None = None
    slug: str = ""
    label: str = ""
    summary: str = ""
    method: str = "heuristic"
    created_at: str = ""
    updated_at: str = ""


@dataclass
class ClusterMember:
    cluster_id: int = 0
    bookmark_id: int = 0
    score: float = 0.0


@dataclass
class ProjectIdea:
    id: int | None = None
    slug: str = ""
    title: str = ""
    one_liner: str = ""
    problem: str = ""
    audience: str = ""
    why_now: str = ""
    implementation_notes: str = ""
    source_cluster_id: int | None = None
    confidence: float = 0.0
    status: str = "candidate"
    created_at: str = ""
    updated_at: str = ""


@dataclass
class ProjectSource:
    project_id: int = 0
    bookmark_id: int = 0
    role: str = "evidence"


@dataclass
class ExportProfile:
    id: int | None = None
    name: str = ""
    adapter: str = "obsidian"
    vault_path: str = ""
    include_categories: list[str] = field(default_factory=list)
    exclude_categories: list[str] = field(default_factory=list)
    exclude_review: bool = False
    include_projects: bool = True
    include_clusters: bool = True
    created_at: str = ""
    updated_at: str = ""


@dataclass
class ExportRun:
    id: int | None = None
    profile_id: int | None = None
    adapter: str = ""
    output_path: str = ""
    exported_count: int = 0
    skipped_count: int = 0
    created_at: str = ""


@dataclass
class CollectionRun:
    id: str = ""
    source: str = "browser"
    started_at: str = ""
    finished_at: str = ""
    status: str = "running"
    seen_count: int = 0
    changed_count: int = 0
    unchanged_count: int = 0
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ClassificationResult:
    primary: str
    categories: list[dict[str, Any]]
    tags: list[str]
    needs_review: bool


@dataclass
class AnalyzeResult:
    bookmark_id: int
    classifications: ClassificationResult
    entities: list[str]
    links: list[str]
    embedding: list[float] | None = None
