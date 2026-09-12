from __future__ import annotations

import math
from collections.abc import Sequence

from .relations import RelatedHit


def mermaid_flowchart(center_id: str, center_label: str, hits: Sequence[RelatedHit]) -> str:
    lines = ["flowchart LR", f'  s{center_id}["{_safe_label(center_label)}"]']
    seen: set[str] = {center_id}
    for hit in hits:
        if hit.status_id not in seen:
            lines.append(f'  s{hit.status_id}["{_safe_label(_hit_label(hit))}"]')
            seen.add(hit.status_id)
        via = _safe_label(hit.via or hit.kind, limit=28)
        lines.append(f"  s{center_id} -- {hit.kind} {via} --> s{hit.status_id}")
    return "\n".join(lines) + "\n"


def ascii_flowchart(center_id: str, center_label: str, hits: Sequence[RelatedHit]) -> str:
    lines = [_box(_safe_label(center_label, limit=36))]
    if not hits:
        lines.append("  (no edges)")
        return "\n".join(lines)
    for index, hit in enumerate(hits):
        branch = "└" if index == len(hits) - 1 else "├"
        label = _safe_label(_hit_label(hit), limit=32)
        via = _safe_label(hit.via, limit=24)
        lines.append(f"  {branch}─[{hit.kind}] {via}")
        lines.append(f"  {' ' if index == len(hits) - 1 else '│'}  {label}")
    return "\n".join(lines)


def category_meters(categories: Sequence[dict], *, width: int = 16, total: int | None = None) -> str:
    if not categories:
        return "no categories"
    peak = max(int(item.get("count") or 0) for item in categories) or 1
    blocks = "▁▂▃▄▅▆▇█"
    lines = []
    for item in categories:
        count = int(item.get("count") or 0)
        filled = int(round((count / peak) * width)) if peak else 0
        wave = blocks[min(len(blocks) - 1, max(0, int((count / peak) * (len(blocks) - 1))))]
        bar = "█" * filled + "░" * (width - filled)
        slug = str(item.get("slug") or "-")
        lines.append(f"{wave} {slug:<12} {bar} {count}")
    return "\n".join(lines)


def sonar_scope(
    *,
    width: int = 42,
    height: int = 18,
    tick: int = 0,
    center_label: str = "CONTACT",
    contacts: Sequence[tuple[str, str]] = (),
) -> str:
    """Polar-ish sonar face. tick rotates the sweep."""
    width = max(24, width)
    height = max(10, height)
    cx, cy = width // 2, height // 2
    grid = [[" " for _ in range(width)] for _ in range(height)]
    max_r = min(cx - 1, cy - 1)
    for ring in (max_r // 3, (max_r * 2) // 3, max_r):
        _ellipse(grid, cx, cy, ring, max(1, ring // 2), "·")
    sweep = (tick * 13) % 360
    rad = math.radians(sweep)
    for radius in range(max_r + 1):
        x = cx + int(round(radius * math.cos(rad)))
        y = cy + int(round(radius * 0.5 * math.sin(rad)))
        _plot(grid, x, y, "━" if radius > 2 else "●")
    _plot(grid, cx, cy, "◈")
    for index, (label, _kind) in enumerate(contacts[:8]):
        angle = (index * 47 + tick * 3) % 360
        dist = max_r - 2 - (index % 3)
        contact_rad = math.radians(angle)
        x = cx + int(round(dist * math.cos(contact_rad)))
        y = cy + int(round(dist * 0.5 * math.sin(contact_rad)))
        blip = "◆" if (tick + index) % 6 < 4 else "◇"
        _plot(grid, x, y, blip)
        _write(grid, x + 1, y, _safe_label(label, limit=10))
    banner = _safe_label(center_label, limit=max(8, width - 18))
    _write(grid, 1, 0, f"RNG {max_r}  HDG {sweep:03d}°  {banner}")
    return "\n".join("".join(row).rstrip() for row in grid)


def _hit_label(hit: RelatedHit) -> str:
    handle = f"@{hit.author_handle}" if hit.author_handle else hit.status_id
    text = " ".join((hit.tweet_text or "").split())
    return f"{handle} {text}".strip()


def _safe_label(text: str, limit: int = 42) -> str:
    compact = " ".join((text or "").split()).replace('"', "'")
    if len(compact) > limit:
        return compact[: limit - 1] + "…"
    return compact


def _box(text: str) -> str:
    inner = f" {text} "
    edge = "─" * len(inner)
    return f"┌{edge}┐\n│{inner}│\n└{edge}┘"


def _plot(grid: list[list[str]], x: int, y: int, char: str) -> None:
    if 0 <= y < len(grid) and 0 <= x < len(grid[0]):
        grid[y][x] = char


def _write(grid: list[list[str]], x: int, y: int, text: str) -> None:
    for offset, char in enumerate(text):
        _plot(grid, x + offset, y, char)


def _ellipse(grid: list[list[str]], cx: int, cy: int, rx: int, ry: int, char: str) -> None:
    if rx <= 0 or ry <= 0:
        return
    for deg in range(0, 360, 6):
        rad = math.radians(deg)
        x = cx + int(round(rx * math.cos(rad)))
        y = cy + int(round(ry * math.sin(rad)))
        _plot(grid, x, y, char)
