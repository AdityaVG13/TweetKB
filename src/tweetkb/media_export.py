from __future__ import annotations

import json
import mimetypes
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from .util import ensure_dir, slugify, stable_hash


@dataclass(frozen=True)
class MediaExportResult:
    tweets: int
    images: int
    downloaded: int
    failed: int
    out_dir: Path


def export_media_bundle(
    store,
    out_dir: Path,
    limit: int | None = None,
    download: bool = True,
    timeout: float = 30.0,
) -> MediaExportResult:
    out_dir = ensure_dir(Path(out_dir))
    images_dir = ensure_dir(out_dir / "images")
    records = _media_records(store, limit=limit)
    downloaded = 0
    failed = 0
    manifest_rows: list[dict[str, Any]] = []

    for index, record in enumerate(records, start=1):
        extension = _image_extension(record["url"])
        filename = _image_filename(record, index, extension)
        image_path = images_dir / filename
        row = {
            **record,
            "file": str(Path("images") / filename),
            "downloaded": False,
            "error": "",
        }
        if download:
            try:
                data, content_type = _download(record["url"], timeout=timeout)
                extension = _image_extension(record["url"], content_type=content_type)
                filename = _image_filename(record, index, extension)
                image_path = images_dir / filename
                row["file"] = str(Path("images") / filename)
                image_path.write_bytes(data)
                row["downloaded"] = True
                downloaded += 1
            except Exception as exc:
                row["error"] = str(exc)
                failed += 1
        manifest_rows.append(row)

    _write_manifest(out_dir, manifest_rows)
    _write_index(out_dir, manifest_rows)
    _write_prompt(out_dir)
    tweet_count = len({row["status_id"] for row in manifest_rows})
    return MediaExportResult(
        tweets=tweet_count,
        images=len(manifest_rows),
        downloaded=downloaded,
        failed=failed,
        out_dir=out_dir,
    )


def _media_records(store, limit: int | None = None) -> list[dict[str, Any]]:
    sql = """
        SELECT
          b.id AS bookmark_id,
          b.status_id,
          b.status_url,
          b.author_handle,
          b.tweet_text,
          b.raw_text,
          ce.metadata_json
        FROM bookmarks b
        JOIN content_enrichments ce ON ce.bookmark_id = b.id
        WHERE b.is_deleted = 0
          AND ce.metadata_json LIKE '%"media"%'
        ORDER BY b.captured_at DESC, b.id DESC, ce.captured_at DESC
    """
    rows = list(store.conn.execute(sql))
    records: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        try:
            metadata = json.loads(row["metadata_json"] or "{}")
        except json.JSONDecodeError:
            metadata = {}
        media_items = metadata.get("media") or []
        if not isinstance(media_items, list):
            continue
        for media_index, media in enumerate(media_items, start=1):
            if not isinstance(media, dict):
                continue
            url = str(media.get("url") or "").strip()
            if not url.startswith(("http://", "https://")):
                continue
            key = (str(row["status_id"]), url)
            if key in seen:
                continue
            seen.add(key)
            records.append(
                {
                    "bookmark_id": int(row["bookmark_id"]),
                    "status_id": str(row["status_id"]),
                    "status_url": row["status_url"],
                    "author_handle": row["author_handle"] or "",
                    "tweet_text": row["tweet_text"] or "",
                    "raw_text": row["raw_text"] or "",
                    "media_index": media_index,
                    "url": url,
                    "alt": str(media.get("alt") or ""),
                }
            )
            if limit is not None and len(records) >= limit:
                return records
    return records


def _download(url: str, timeout: float) -> tuple[bytes, str]:
    request = urllib.request.Request(url, headers={"User-Agent": "TweetKB/0.4"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read(50 * 1024 * 1024), response.headers.get("Content-Type", "")


def _image_extension(url: str, content_type: str = "") -> str:
    parsed = urlparse(url)
    query_format = parse_qs(parsed.query).get("format", [""])[0].lower()
    if query_format in {"jpg", "jpeg", "png", "webp", "gif"}:
        return ".jpg" if query_format == "jpeg" else f".{query_format}"
    guessed = mimetypes.guess_extension((content_type or "").split(";")[0].strip())
    if guessed in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        return ".jpg" if guessed == ".jpeg" else guessed
    suffix = Path(parsed.path).suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        return ".jpg" if suffix == ".jpeg" else suffix
    return ".jpg"


def _image_filename(record: dict[str, Any], index: int, extension: str) -> str:
    handle = slugify(record.get("author_handle", ""), fallback="author")
    status_id = slugify(record.get("status_id", ""), fallback="status")
    digest = stable_hash(record["url"])[:10]
    return f"{index:04d}-{handle}-{status_id}-{record['media_index']}-{digest}{extension}"


def _write_manifest(out_dir: Path, rows: list[dict[str, Any]]) -> None:
    with (out_dir / "manifest.jsonl").open("w") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _write_index(out_dir: Path, rows: list[dict[str, Any]]) -> None:
    lines = [
        "# TweetKB Media Review Bundle",
        "",
        "Images exported from captured X/Twitter bookmark enrichment metadata.",
        "",
        "| File | Tweet | Author | Alt text |",
        "| --- | --- | --- | --- |",
    ]
    for row in rows:
        file_ref = row["file"] if row["downloaded"] else row["url"]
        tweet = row["status_url"]
        author = f"@{row['author_handle']}" if row["author_handle"] else ""
        alt = " ".join(row["alt"].split())[:160]
        lines.append(f"| `{file_ref}` | {tweet} | {author} | {alt} |")
    (out_dir / "index.md").write_text("\n".join(lines) + "\n")


def _write_prompt(out_dir: Path) -> None:
    prompt = """You are analyzing an exported TweetKB media bundle.

Open `manifest.jsonl` and inspect every downloaded image under `images/`.
For each image:
- Identify visible UI, diagrams, charts, code, product screenshots, memes, and documents.
- Transcribe important text in the image.
- Explain why the image may matter in the context of the linked tweet.
- Note low-information images, duplicates, or images that need manual review.

Return a concise Markdown report grouped by tweet URL. Include image filenames so
the findings can be imported back into TweetKB later.
"""
    (out_dir / "AI_REVIEW_PROMPT.md").write_text(prompt)
