from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .util import ensure_dir, extract_status_id, normalize_status_url, stable_hash

DEFAULT_DB = Path("data/bookmarks.sqlite3")


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS bookmarks (
  id INTEGER PRIMARY KEY,
  status_id TEXT UNIQUE,
  status_url TEXT,
  author_name TEXT,
  author_handle TEXT,
  tweet_text TEXT NOT NULL DEFAULT '',
  raw_text TEXT NOT NULL DEFAULT '',
  created_at TEXT,
  captured_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  category TEXT NOT NULL DEFAULT 'misc',
  confidence REAL NOT NULL DEFAULT 0,
  summary TEXT NOT NULL DEFAULT '',
  why_it_matters TEXT NOT NULL DEFAULT '',
  use_cases_json TEXT NOT NULL DEFAULT '[]',
  entities_json TEXT NOT NULL DEFAULT '[]',
  links_json TEXT NOT NULL DEFAULT '[]',
  needs_review INTEGER NOT NULL DEFAULT 1,
  review_note TEXT NOT NULL DEFAULT '',
  content_hash TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS tags (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS bookmark_tags (
  bookmark_id INTEGER NOT NULL REFERENCES bookmarks(id) ON DELETE CASCADE,
  tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
  PRIMARY KEY (bookmark_id, tag_id)
);

CREATE TABLE IF NOT EXISTS embeddings (
  bookmark_id INTEGER PRIMARY KEY REFERENCES bookmarks(id) ON DELETE CASCADE,
  dims INTEGER NOT NULL,
  vector_json TEXT NOT NULL,
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS processing_events (
  id INTEGER PRIMARY KEY,
  bookmark_id INTEGER REFERENCES bookmarks(id) ON DELETE SET NULL,
  event_type TEXT NOT NULL,
  message TEXT NOT NULL DEFAULT '',
  payload_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE VIRTUAL TABLE IF NOT EXISTS bookmarks_fts
USING fts5(tweet_text, summary, why_it_matters, author_name, author_handle, content='bookmarks', content_rowid='id');

CREATE TRIGGER IF NOT EXISTS bookmarks_ai AFTER INSERT ON bookmarks BEGIN
  INSERT INTO bookmarks_fts(rowid, tweet_text, summary, why_it_matters, author_name, author_handle)
  VALUES (new.id, new.tweet_text, new.summary, new.why_it_matters, new.author_name, new.author_handle);
END;

CREATE TRIGGER IF NOT EXISTS bookmarks_ad AFTER DELETE ON bookmarks BEGIN
  INSERT INTO bookmarks_fts(bookmarks_fts, rowid, tweet_text, summary, why_it_matters, author_name, author_handle)
  VALUES('delete', old.id, old.tweet_text, old.summary, old.why_it_matters, old.author_name, old.author_handle);
END;

CREATE TRIGGER IF NOT EXISTS bookmarks_au AFTER UPDATE ON bookmarks BEGIN
  INSERT INTO bookmarks_fts(bookmarks_fts, rowid, tweet_text, summary, why_it_matters, author_name, author_handle)
  VALUES('delete', old.id, old.tweet_text, old.summary, old.why_it_matters, old.author_name, old.author_handle);
  INSERT INTO bookmarks_fts(rowid, tweet_text, summary, why_it_matters, author_name, author_handle)
  VALUES (new.id, new.tweet_text, new.summary, new.why_it_matters, new.author_name, new.author_handle);
END;
"""


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
        self.conn.executescript(SCHEMA)
        self.conn.commit()

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

        row = self.conn.execute("SELECT id, content_hash FROM bookmarks WHERE status_id = ?", (status_id,)).fetchone()
        if row and row["content_hash"] == content_hash:
            return int(row["id"]), False

        self.conn.execute(
            """
            INSERT INTO bookmarks (
              status_id, status_url, author_name, author_handle, tweet_text, raw_text,
              created_at, links_json, content_hash, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(status_id) DO UPDATE SET
              status_url=excluded.status_url,
              author_name=excluded.author_name,
              author_handle=excluded.author_handle,
              tweet_text=excluded.tweet_text,
              raw_text=excluded.raw_text,
              created_at=excluded.created_at,
              links_json=excluded.links_json,
              content_hash=excluded.content_hash,
              updated_at=datetime('now')
            """,
            (
                status_id,
                status_url,
                data.get("author_name") or "",
                author_handle,
                tweet_text,
                raw_text,
                data.get("created_at") or "",
                json.dumps(links, ensure_ascii=True),
                content_hash,
            ),
        )
        self.conn.commit()
        saved = self.conn.execute("SELECT id FROM bookmarks WHERE status_id = ?", (status_id,)).fetchone()
        return (int(saved["id"]), True) if saved else None

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

    def set_embedding(self, bookmark_id: int, vector: list[float]) -> None:
        self.conn.execute(
            """
            INSERT INTO embeddings(bookmark_id, dims, vector_json, updated_at)
            VALUES (?, ?, ?, datetime('now'))
            ON CONFLICT(bookmark_id) DO UPDATE SET
              dims=excluded.dims,
              vector_json=excluded.vector_json,
              updated_at=datetime('now')
            """,
            (bookmark_id, len(vector), json.dumps(vector)),
        )
        self.conn.commit()

    def update_classification(self, bookmark_id: int, result: dict[str, Any]) -> None:
        self.conn.execute(
            """
            UPDATE bookmarks SET
              category=?,
              confidence=?,
              summary=?,
              why_it_matters=?,
              use_cases_json=?,
              entities_json=?,
              needs_review=?,
              updated_at=datetime('now')
            WHERE id=?
            """,
            (
                result["category"],
                float(result["confidence"]),
                result["summary"],
                result["why_it_matters"],
                json.dumps(result["use_cases"], ensure_ascii=True),
                json.dumps(result["entities"], ensure_ascii=True),
                1 if result["needs_review"] else 0,
                bookmark_id,
            ),
        )
        self.conn.commit()
        self.add_tags(bookmark_id, result["tags"])

    def list_bookmarks(self, category: str | None = None, needs_review: bool | None = None, q: str | None = None) -> list[sqlite3.Row]:
        params: list[Any] = []
        where = []
        join = ""
        if category:
            where.append("b.category = ?")
            params.append(category)
        if needs_review is not None:
            where.append("b.needs_review = ?")
            params.append(1 if needs_review else 0)
        if q:
            join = "JOIN bookmarks_fts f ON f.rowid = b.id"
            where.append("bookmarks_fts MATCH ?")
            params.append(q)
        sql = f"SELECT b.* FROM bookmarks b {join}"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY b.captured_at DESC, b.id DESC"
        return list(self.conn.execute(sql, params))

    def get_bookmark(self, bookmark_id: int) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM bookmarks WHERE id = ?", (bookmark_id,)).fetchone()

    def stats(self) -> dict[str, Any]:
        total = self.conn.execute("SELECT count(*) c FROM bookmarks").fetchone()["c"]
        review = self.conn.execute("SELECT count(*) c FROM bookmarks WHERE needs_review = 1").fetchone()["c"]
        cats = self.conn.execute("SELECT category, count(*) c FROM bookmarks GROUP BY category ORDER BY c DESC").fetchall()
        return {"total": total, "needs_review": review, "categories": {r["category"]: r["c"] for r in cats}}

    def log_event(self, event_type: str, message: str = "", payload: dict[str, Any] | None = None, bookmark_id: int | None = None) -> None:
        self.conn.execute(
            "INSERT INTO processing_events(bookmark_id, event_type, message, payload_json) VALUES (?, ?, ?, ?)",
            (bookmark_id, event_type, message, json.dumps(payload or {}, ensure_ascii=True)),
        )
        self.conn.commit()
