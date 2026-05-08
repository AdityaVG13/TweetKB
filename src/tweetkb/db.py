from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .migrations import migrate
from .util import ensure_dir, extract_status_id, normalize_status_url, stable_hash

DEFAULT_DB = Path("data/bookmarks.sqlite3")


@dataclass(frozen=True)
class BookmarkInput:
    status_url: str | None
    author_name: str = ""
    author_handle: str = ""
    tweet_text: str = ""
    raw_text: str = ""
    created_at: str = ""
    links: tuple[str, ...] = ()


class Store:
    def __init__(self, path: Path = DEFAULT_DB):
        self.path = Path(path)
        ensure_dir(self.path.parent)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")

    def close(self) -> None:
        self.conn.close()

    def init(self) -> None:
        migrate(self.conn)

    def schema_version(self) -> int:
        try:
            row = self.conn.execute("SELECT version FROM schema_migrations ORDER BY version DESC LIMIT 1").fetchone()
            return int(row["version"]) if row else 0
        except sqlite3.OperationalError:
            return 0

    def upsert_bookmark(self, item: BookmarkInput | dict[str, Any]) -> int | None:
        result = self.upsert_bookmark_with_status(item)
        return result[0] if result else None

    def upsert_bookmark_with_status(self, item: BookmarkInput | dict[str, Any]) -> tuple[int, bool] | None:
        data = item if isinstance(item, dict) else item.__dict__
        status_url = data.get("status_url") or data.get("url")
        status_id = data.get("status_id") or extract_status_id(status_url)
        if not status_id:
            return None
        author_handle = (data.get("author_handle") or data.get("handle") or "").lstrip("@")
        status_url = normalize_status_url(status_url, author_handle, status_id)
        tweet_text = (data.get("tweet_text") or data.get("text") or "").strip()
        raw_text = (data.get("raw_text") or tweet_text).strip()
        links = tuple(dict.fromkeys(data.get("links") or ()))
        content_hash = stable_hash("\n".join([status_id, tweet_text, raw_text, json.dumps(links, sort_keys=True)]))
        now = datetime.now(timezone.utc).isoformat()

        row = self.conn.execute("SELECT id, content_hash FROM bookmarks WHERE status_id = ?", (status_id,)).fetchone()
        if row and row["content_hash"] == content_hash:
            self._store_bookmark_links(int(row["id"]), links)
            return int(row["id"]), False

        # Upsert author
        author_id: int | None = None
        if author_handle:
            self.conn.execute(
                """INSERT INTO authors(handle, display_name, first_seen_at, last_seen_at)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(handle) DO UPDATE SET
                     display_name=COALESCE(excluded.display_name, authors.display_name),
                     last_seen_at=excluded.last_seen_at""",
                (author_handle, data.get("author_name") or "", now, now),
            )
            author_row = self.conn.execute("SELECT id FROM authors WHERE handle = ?", (author_handle,)).fetchone()
            if author_row:
                author_id = int(author_row["id"])

        self.conn.execute(
            """
            INSERT INTO bookmarks (
              status_id, status_url, author_id, author_name, author_handle, tweet_text, raw_text,
              created_at, content_hash, captured_at, updated_at, collection_source
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(status_id) DO UPDATE SET
              status_url=excluded.status_url,
              author_id=excluded.author_id,
              author_name=excluded.author_name,
              author_handle=excluded.author_handle,
              tweet_text=excluded.tweet_text,
              raw_text=excluded.raw_text,
              created_at=excluded.created_at,
              content_hash=excluded.content_hash,
              updated_at=datetime('now')
            """,
            (
                status_id,
                status_url,
                author_id,
                data.get("author_name") or "",
                author_handle,
                tweet_text,
                raw_text,
                data.get("created_at") or "",
                content_hash,
                now,
                now,
                "browser",
            ),
        )
        self.conn.commit()
        saved = self.conn.execute("SELECT id FROM bookmarks WHERE status_id = ?", (status_id,)).fetchone()
        if not saved:
            return None
        bookmark_id = int(saved["id"])
        self._store_bookmark_links(bookmark_id, links)
        return bookmark_id, True

    def _store_bookmark_links(self, bookmark_id: int, links: tuple[str, ...]) -> None:
        for url in links:
            link_id = self.upsert_link(url)
            if link_id:
                self.add_bookmark_link(bookmark_id, link_id)

    def upsert_link(self, url: str) -> int | None:
        if not url:
            return None
        from urllib.parse import urlparse

        domain = ""
        try:
            domain = urlparse(url).netloc.lower().removeprefix("www.")
        except Exception:
            pass
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            """INSERT INTO links(url, domain, first_seen_at, last_seen_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(url) DO UPDATE SET
                 domain=COALESCE(excluded.domain, links.domain),
                 last_seen_at=excluded.last_seen_at""",
            (url, domain, now, now),
        )
        self.conn.commit()
        row = self.conn.execute("SELECT id FROM links WHERE url = ?", (url,)).fetchone()
        return int(row["id"]) if row else None

    def upsert_entity(self, name: str, entity_type: str = "other", source: str = "text-regex") -> int | None:
        if not name:
            return None
        normalized = name.lower().strip()
        self.conn.execute(
            """INSERT INTO entities(name, normalized_name, type, source)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(normalized_name, type) DO NOTHING""",
            (name, normalized, entity_type, source),
        )
        self.conn.commit()
        row = self.conn.execute("SELECT id FROM entities WHERE normalized_name = ? AND type = ?", (normalized, entity_type)).fetchone()
        return int(row["id"]) if row else None

    def add_bookmark_link(self, bookmark_id: int, link_id: int, role: str = "mentioned") -> None:
        self.conn.execute(
            "INSERT OR IGNORE INTO bookmark_links(bookmark_id, link_id, role) VALUES (?, ?, ?)",
            (bookmark_id, link_id, role),
        )
        self.conn.commit()

    def add_bookmark_entity(
        self, bookmark_id: int, entity_id: int, salience: float = 0.5, evidence: str = ""
    ) -> None:
        self.conn.execute(
            "INSERT OR IGNORE INTO bookmark_entities(bookmark_id, entity_id, salience, evidence) VALUES (?, ?, ?, ?)",
            (bookmark_id, entity_id, salience, evidence),
        )
        self.conn.commit()

    def add_tags(self, bookmark_id: int, tags: Iterable[str]) -> None:
        for tag in sorted({t.strip().lower() for t in tags if t and t.strip()}):
            self.conn.execute("INSERT OR IGNORE INTO tags(name) VALUES (?)", (tag,))
            row = self.conn.execute("SELECT id FROM tags WHERE name = ?", (tag,)).fetchone()
            if row:
                self.conn.execute(
                    "INSERT OR IGNORE INTO bookmark_tags(bookmark_id, tag_id) VALUES (?, ?)",
                    (bookmark_id, int(row["id"])),
                )
        self.conn.commit()

    def set_embedding(
        self,
        bookmark_id: int,
        vector: list[float],
        provider: str = "local-hash",
        model: str = "hash-v1",
        content_hash: str = "",
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            """INSERT INTO embeddings(bookmark_id, provider, model, dims, vector_json, content_hash, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(bookmark_id, provider, model) DO UPDATE SET
                 dims=excluded.dims,
                 vector_json=excluded.vector_json,
                 content_hash=excluded.content_hash,
                 updated_at=excluded.updated_at""",
            (bookmark_id, provider, model, len(vector), json.dumps(vector), content_hash, now),
        )
        self.conn.commit()

    def analysis_state_current(self, bookmark_id: int, stage: str, provider: str, content_hash: str) -> bool:
        row = self.conn.execute(
            """SELECT content_hash FROM analysis_state
               WHERE bookmark_id = ? AND stage = ? AND provider = ?""",
            (bookmark_id, stage, provider),
        ).fetchone()
        return bool(row and row["content_hash"] == content_hash)

    def set_analysis_state(self, bookmark_id: int, stage: str, provider: str, content_hash: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            """INSERT INTO analysis_state(bookmark_id, stage, provider, content_hash, updated_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(bookmark_id, stage, provider) DO UPDATE SET
                 content_hash=excluded.content_hash,
                 updated_at=excluded.updated_at""",
            (bookmark_id, stage, provider, content_hash, now),
        )
        self.conn.commit()

    def set_content_enrichment(
        self,
        bookmark_id: int,
        source_url: str,
        content_text: str,
        source_type: str = "x-status",
        title: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        content_text = (content_text or "").strip()
        if not content_text:
            return False
        content_hash = stable_hash("\n".join([source_url, source_type, title, content_text]))
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            """INSERT INTO content_enrichments
               (bookmark_id, source_url, source_type, title, content_text, content_hash, captured_at, metadata_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(bookmark_id, source_url) DO UPDATE SET
                 source_type=excluded.source_type,
                 title=excluded.title,
                 content_text=excluded.content_text,
                 content_hash=excluded.content_hash,
                 captured_at=excluded.captured_at,
                 metadata_json=excluded.metadata_json""",
            (
                bookmark_id,
                source_url,
                source_type,
                title,
                content_text,
                content_hash,
                now,
                json.dumps(metadata or {}, ensure_ascii=True, sort_keys=True),
            ),
        )
        self.conn.commit()
        return True

    def get_content_enrichment(self, bookmark_id: int) -> sqlite3.Row | None:
        return self.conn.execute(
            """SELECT * FROM content_enrichments
               WHERE bookmark_id = ?
               ORDER BY
                 CASE source_type
                   WHEN 'x-article' THEN 0
                   WHEN 'x-status' THEN 1
                   WHEN 'x-conversation' THEN 2
                   WHEN 'linked-page' THEN 3
                   ELSE 4
                 END,
                 captured_at DESC
               LIMIT 1""",
            (bookmark_id,),
        ).fetchone()

    def get_content_enrichments(self, bookmark_id: int) -> list[sqlite3.Row]:
        return list(
            self.conn.execute(
                """SELECT * FROM content_enrichments
                   WHERE bookmark_id = ?
                   ORDER BY
                     CASE source_type
                       WHEN 'x-article' THEN 0
                       WHEN 'x-status' THEN 1
                       WHEN 'x-conversation' THEN 2
                       WHEN 'linked-page' THEN 3
                       ELSE 4
                     END,
                     captured_at DESC""",
                (bookmark_id,),
            )
        )

    def list_bookmarks_for_enrichment(
        self,
        category: str | None = None,
        since: str | None = None,
        limit: int | None = None,
        missing_only: bool = True,
        missing_source_type: str | None = None,
    ) -> list[sqlite3.Row]:
        join_params: list[Any] = []
        where_params: list[Any] = []
        joins = []
        where = ["b.is_deleted = 0"]
        if category:
            joins.append("JOIN classifications cl ON cl.bookmark_id = b.id AND cl.is_primary = 1")
            where.append("cl.category_slug = ?")
            where_params.append(category)
        if since:
            where.append("date(b.captured_at) >= date(?)")
            where_params.append(since)
        if missing_only:
            if missing_source_type:
                joins.append("LEFT JOIN content_enrichments ce ON ce.bookmark_id = b.id AND ce.source_type = ?")
                join_params.append(missing_source_type)
            else:
                joins.append("LEFT JOIN content_enrichments ce ON ce.bookmark_id = b.id")
            where.append("ce.id IS NULL")

        params = [*join_params, *where_params]
        sql = "SELECT DISTINCT b.* FROM bookmarks b " + " ".join(joins)
        sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY b.captured_at DESC, b.id DESC"
        if limit:
            sql += " LIMIT ?"
            params.append(limit)
        return list(self.conn.execute(sql, params))

    def set_classifications(
        self,
        bookmark_id: int,
        classifications: list[dict[str, Any]],
        primary: str,
        confidence: float,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        # Delete existing
        self.conn.execute("DELETE FROM classifications WHERE bookmark_id = ?", (bookmark_id,))
        # Insert new
        for cls in classifications:
            self.conn.execute(
                """INSERT INTO classifications
                   (bookmark_id, category_slug, confidence, method, rationale, is_primary, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    bookmark_id,
                    cls["slug"],
                    float(cls["confidence"]),
                    cls.get("method", "keyword"),
                    cls.get("rationale", ""),
                    1 if cls["slug"] == primary else 0,
                    now,
                ),
            )
        self.conn.commit()

    def update_bookmark_analysis(
        self,
        bookmark_id: int,
        summary: str = "",
        why_it_matters: str = "",
        needs_review: bool = True,
        review_note: str = "",
    ) -> None:
        self.conn.execute(
            """UPDATE bookmarks SET
               summary=?,
               why_it_matters=?,
               needs_review=?,
               review_note=?,
               updated_at=datetime('now')
               WHERE id=?""",
            (
                summary,
                why_it_matters,
                1 if needs_review else 0,
                review_note,
                bookmark_id,
            ),
        )
        self.conn.commit()

    def list_bookmarks(
        self,
        category: str | None = None,
        needs_review: bool | None = None,
        q: str | None = None,
        review_state: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[sqlite3.Row]:
        params: list[Any] = []
        where = ["b.is_deleted = 0"]
        join = ""

        if category:
            where.append("c.slug = ?")
            params.append(category)
            join = "JOIN classifications c ON c.bookmark_id = b.id AND c.is_primary = 1"
        if needs_review is not None:
            where.append("b.needs_review = ?")
            params.append(1 if needs_review else 0)
        if review_state:
            where.append("b.review_state = ?")
            params.append(review_state)
        if q:
            join = "JOIN bookmarks_fts f ON f.rowid = b.id"
            where.append("bookmarks_fts MATCH ?")
            params.append(q)

        sql = f"SELECT DISTINCT b.* FROM bookmarks b {join}"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY b.captured_at DESC, b.id DESC"
        if limit:
            sql += f" LIMIT {limit} OFFSET {offset}"
        return list(self.conn.execute(sql, params))

    def list_bookmarks_for_analysis(
        self,
        changed_only: bool = False,
        include_categories: set[str] | None = None,
        exclude_categories: set[str] | None = None,
        needs_review: bool | None = None,
        review_state: str | None = None,
        limit: int | None = None,
    ) -> list[sqlite3.Row]:
        params: list[Any] = []
        joins: list[str] = []
        where = ["b.is_deleted = 0"]

        if changed_only:
            joins.append("LEFT JOIN embeddings e ON e.bookmark_id = b.id")
            where.append("e.id IS NULL")
        if include_categories:
            placeholders = ",".join("?" for _ in include_categories)
            where.append(
                "EXISTS ("
                "SELECT 1 FROM classifications ac "
                "WHERE ac.bookmark_id = b.id AND ac.category_slug IN "
                f"({placeholders})"
                ")"
            )
            params.extend(sorted(include_categories))
        if exclude_categories:
            placeholders = ",".join("?" for _ in exclude_categories)
            where.append(
                "NOT EXISTS ("
                "SELECT 1 FROM classifications xc "
                "WHERE xc.bookmark_id = b.id AND xc.category_slug IN "
                f"({placeholders})"
                ")"
            )
            params.extend(sorted(exclude_categories))
        if needs_review is not None:
            where.append("b.needs_review = ?")
            params.append(1 if needs_review else 0)
        if review_state:
            where.append("b.review_state = ?")
            params.append(review_state)

        sql = f"SELECT DISTINCT b.* FROM bookmarks b {' '.join(joins)}"
        sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY b.id"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(int(limit))
        return list(self.conn.execute(sql, params))

    def get_bookmark(self, bookmark_id: int) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM bookmarks WHERE id = ?", (bookmark_id,)).fetchone()

    def get_bookmark_by_status(self, status_id: str) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM bookmarks WHERE status_id = ?", (status_id,)).fetchone()

    def get_bookmark_entities(self, bookmark_id: int) -> list[sqlite3.Row]:
        return list(
            self.conn.execute(
                """SELECT e.*, be.salience, be.evidence FROM entities e
                   JOIN bookmark_entities be ON be.entity_id = e.id
                   WHERE be.bookmark_id = ?
                   ORDER BY be.salience DESC""",
                (bookmark_id,),
            )
        )

    def get_bookmark_links(self, bookmark_id: int) -> list[sqlite3.Row]:
        return list(
            self.conn.execute(
                """SELECT l.* FROM links l
                   JOIN bookmark_links bl ON bl.link_id = l.id
                   WHERE bl.bookmark_id = ?
                   ORDER BY l.id""",
                (bookmark_id,),
            )
        )

    def get_bookmark_classifications(self, bookmark_id: int) -> list[sqlite3.Row]:
        return list(
            self.conn.execute(
                """SELECT c.* FROM classifications c
                   WHERE c.bookmark_id = ?
                   ORDER BY c.is_primary DESC, c.confidence DESC""",
                (bookmark_id,),
            )
        )

    def get_bookmark_tags(self, bookmark_id: int) -> list[str]:
        rows = list(
            self.conn.execute(
                """SELECT t.name FROM tags t
                   JOIN bookmark_tags bt ON bt.tag_id = t.id
                   WHERE bt.bookmark_id = ?""",
                (bookmark_id,),
            )
        )
        return [r["name"] for r in rows]

    def get_categories(self) -> list[sqlite3.Row]:
        return list(self.conn.execute("SELECT * FROM categories ORDER BY label"))

    def get_category(self, slug: str) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM categories WHERE slug = ?", (slug,)).fetchone()

    def get_clusters(self) -> list[sqlite3.Row]:
        return list(self.conn.execute("SELECT * FROM clusters ORDER BY created_at DESC"))

    def get_cluster_members(self, cluster_id: int) -> list[sqlite3.Row]:
        return list(
            self.conn.execute(
                """SELECT b.*, cm.score FROM bookmarks b
                   JOIN cluster_members cm ON cm.bookmark_id = b.id
                   WHERE cm.cluster_id = ?
                   ORDER BY cm.score DESC""",
                (cluster_id,),
            )
        )

    def get_projects(self, status: str | None = None) -> list[sqlite3.Row]:
        if status:
            return list(
                self.conn.execute(
                    "SELECT * FROM project_ideas WHERE status = ? ORDER BY confidence DESC",
                    (status,),
                )
            )
        return list(self.conn.execute("SELECT * FROM project_ideas ORDER BY confidence DESC"))

    def get_project_sources(self, project_id: int) -> list[sqlite3.Row]:
        return list(
            self.conn.execute(
                """SELECT b.*, ps.role FROM bookmarks b
                   JOIN project_sources ps ON ps.bookmark_id = b.id
                   WHERE ps.project_id = ?""",
                (project_id,),
            )
        )

    def get_entities(self, entity_type: str | None = None, min_mentions: int = 1) -> list[sqlite3.Row]:
        if entity_type:
            return list(
                self.conn.execute(
                    """SELECT e.*, COUNT(be.bookmark_id) as mention_count
                       FROM entities e
                       JOIN bookmark_entities be ON be.entity_id = e.id
                       WHERE e.type = ?
                       GROUP BY e.id
                       HAVING mention_count >= ?
                       ORDER BY mention_count DESC""",
                    (entity_type, min_mentions),
                )
            )
        return list(
            self.conn.execute(
                """SELECT e.*, COUNT(be.bookmark_id) as mention_count
                   FROM entities e
                   JOIN bookmark_entities be ON be.entity_id = e.id
                   GROUP BY e.id
                   HAVING mention_count >= ?
                   ORDER BY mention_count DESC""",
                (min_mentions,),
            )
        )

    def get_top_entities(self, limit: int = 20) -> list[sqlite3.Row]:
        return list(
            self.conn.execute(
                """SELECT e.*, COUNT(be.bookmark_id) as mention_count
                   FROM entities e
                   JOIN bookmark_entities be ON be.entity_id = e.id
                   GROUP BY e.id
                   ORDER BY mention_count DESC
                   LIMIT ?""",
                (limit,),
            )
        )

    def get_top_authors(self, limit: int = 20) -> list[sqlite3.Row]:
        return list(
            self.conn.execute(
                """SELECT a.*, COUNT(b.id) as actual_bookmark_count
                   FROM authors a
                   JOIN bookmarks b ON b.author_id = a.id
                   WHERE b.is_deleted = 0
                   GROUP BY a.id
                   ORDER BY actual_bookmark_count DESC
                   LIMIT ?""",
                (limit,),
            )
        )

    def get_top_domains(self, limit: int = 20) -> list[sqlite3.Row]:
        return list(
            self.conn.execute(
                """SELECT domain, COUNT(*) as link_count
                   FROM links
                   WHERE domain != ''
                   GROUP BY domain
                   ORDER BY link_count DESC
                   LIMIT ?""",
                (limit,),
            )
        )

    def stats(self) -> dict[str, Any]:
        total = self.conn.execute("SELECT count(*) c FROM bookmarks WHERE is_deleted = 0").fetchone()["c"]
        needs_review = self.conn.execute("SELECT count(*) c FROM bookmarks WHERE needs_review = 1 AND is_deleted = 0").fetchone()["c"]
        approved = self.conn.execute("SELECT count(*) c FROM bookmarks WHERE review_state = 'approved' AND is_deleted = 0").fetchone()["c"]
        excluded = self.conn.execute("SELECT count(*) c FROM bookmarks WHERE review_state = 'excluded' AND is_deleted = 0").fetchone()["c"]
        archived = self.conn.execute("SELECT count(*) c FROM bookmarks WHERE is_archived = 1 AND is_deleted = 0").fetchone()["c"]

        cats = self.conn.execute(
            """SELECT c.slug, c.label, COUNT(cl.id) as count
               FROM categories c
               LEFT JOIN classifications cl ON cl.category_slug = c.slug AND cl.is_primary = 1
               LEFT JOIN bookmarks b ON b.id = cl.bookmark_id AND b.is_deleted = 0
               GROUP BY c.id
               ORDER BY count DESC"""
        ).fetchall()

        entities = self.get_top_entities(limit=10)
        authors = self.get_top_authors(limit=10)
        domains = self.get_top_domains(limit=10)
        projects = self.conn.execute("SELECT count(*) c FROM project_ideas WHERE status = 'candidate'").fetchone()["c"]
        clusters = self.conn.execute("SELECT count(*) c FROM clusters").fetchone()["c"]

        return {
            "total": total,
            "needs_review": needs_review,
            "approved": approved,
            "excluded": excluded,
            "archived": archived,
            "project_candidates": projects,
            "clusters": clusters,
            "categories": {r["slug"]: {"label": r["label"], "count": r["count"]} for r in cats},
            "top_entities": [{"name": r["name"], "type": r["type"], "mentions": r["mention_count"]} for r in entities],
            "top_authors": [{"handle": r["handle"], "display_name": r["display_name"], "count": r["actual_bookmark_count"]} for r in authors],
            "top_domains": [{"domain": r["domain"], "count": r["link_count"]} for r in domains],
        }

    def review_bookmark(self, bookmark_id: int, state: str, note: str = "") -> None:
        self.conn.execute(
            "UPDATE bookmarks SET review_state = ?, review_note = ?, needs_review = 0, updated_at = datetime('now') WHERE id = ?",
            (state, note, bookmark_id),
        )
        self.conn.commit()

    def set_review_state(self, bookmark_id: int, state: str) -> None:
        self.conn.execute(
            "UPDATE bookmarks SET review_state = ?, needs_review = 0, updated_at = datetime('now') WHERE id = ?",
            (state, bookmark_id),
        )
        self.conn.commit()

    def log_event(
        self,
        event_type: str,
        message: str = "",
        payload: dict[str, Any] | None = None,
        bookmark_id: int | None = None,
    ) -> None:
        self.conn.execute(
            "INSERT INTO processing_events(bookmark_id, event_type, message, payload_json) VALUES (?, ?, ?, ?)",
            (bookmark_id, event_type, message, json.dumps(payload or {}, ensure_ascii=True)),
        )
        self.conn.commit()

    def log_collection_run(
        self,
        run_id: str,
        source: str,
        seen: int,
        changed: int,
        unchanged: int,
        status: str = "completed",
        error: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            """INSERT INTO collection_runs(id, source, started_at, finished_at, status, seen_count, changed_count, unchanged_count, error, metadata_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (run_id, source, now, now, status, seen, changed, unchanged, error, json.dumps(metadata or {}, ensure_ascii=True)),
        )
        self.conn.commit()

    def log_export_run(
        self,
        adapter: str,
        output_path: str,
        exported: int,
        skipped: int,
        profile_id: int | None = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            """INSERT INTO export_runs(profile_id, adapter, output_path, exported_count, skipped_count, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (profile_id, adapter, output_path, exported, skipped, now),
        )
        self.conn.commit()

    def vacuum(self) -> None:
        self.conn.execute("VACUUM")
        self.conn.commit()

    def page_stats(self) -> dict[str, Any]:
        try:
            page_size = self.conn.execute("PRAGMA page_size").fetchone()[0]
            page_count = self.conn.execute("PRAGMA page_count").fetchone()[0]
            freelist_count = self.conn.execute("PRAGMA freelist_count").fetchone()[0]
            file_size = self.path.stat().st_size if self.path.exists() else 0
            bookmark_count = self.conn.execute("SELECT count(*) FROM bookmarks WHERE is_deleted = 0").fetchone()[0]
            link_count = self.conn.execute("SELECT count(*) FROM links").fetchone()[0]
            entity_count = self.conn.execute("SELECT count(*) FROM entities").fetchone()[0]
            embedding_count = self.conn.execute("SELECT count(*) FROM embeddings").fetchone()[0]
            return {
                "database_path": str(self.path),
                "file_size_bytes": file_size,
                "page_size": page_size,
                "page_count": page_count,
                "freelist_count": freelist_count,
                "bookmark_count": bookmark_count,
                "link_count": link_count,
                "entity_count": entity_count,
                "embedding_count": embedding_count,
                "estimated_reclaimable_bytes": freelist_count * page_size,
            }
        except Exception as e:
            return {"error": str(e)}
