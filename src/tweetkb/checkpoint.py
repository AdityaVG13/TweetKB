from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .util import ensure_dir

DEFAULT_CHECKPOINT = Path("data/checkpoint.json")


class Checkpoint:
    def __init__(self, path: Path = DEFAULT_CHECKPOINT):
        self.path = Path(path)
        ensure_dir(self.path.parent)

    def read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"seen_status_ids": [], "batches": 0}
        return json.loads(self.path.read_text())

    def write(self, data: dict[str, Any]) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True))
        tmp.replace(self.path)

    def add_seen(self, status_ids: list[str]) -> None:
        data = self.read()
        seen = set(data.get("seen_status_ids", []))
        seen.update(s for s in status_ids if s)
        data["seen_status_ids"] = sorted(seen)
        data["batches"] = int(data.get("batches", 0)) + 1
        self.write(data)

