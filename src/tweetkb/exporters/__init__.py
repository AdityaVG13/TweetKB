from __future__ import annotations

from .csv import export_csv
from .jsonl import export_jsonl
from .logseq import export_logseq
from .markdown import export_markdown
from .obsidian import export_obsidian

ADAPTERS = {
    "obsidian": export_obsidian,
    "logseq": export_logseq,
    "markdown": export_markdown,
    "jsonl": export_jsonl,
    "csv": export_csv,
}


def get_adapter(name: str):
    return ADAPTERS.get(name.lower())


def list_adapters():
    return list(ADAPTERS.keys())
