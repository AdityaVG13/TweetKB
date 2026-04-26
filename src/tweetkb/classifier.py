from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

from .categories import CATEGORIES, KEYWORDS
from .util import link_domain

WORD_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9_+-]{1,}")
ENTITY_RE = re.compile(r"\b(?:[A-Z][A-Za-z0-9]+(?:\s+[A-Z][A-Za-z0-9]+){0,3}|GPT-\d(?:\.\d)?|Claude|Gemini|Llama|Qwen|MCP|API|SDK)\b")


def classify_text(text: str, links: list[str] | tuple[str, ...] = ()) -> dict[str, Any]:
    lower = text.lower()
    scores = {cat: 0 for cat in CATEGORIES}
    for cat, words in KEYWORDS.items():
        for word in words:
            if word in lower:
                scores[cat] += 2 if " " in word else 1
    for url in links:
        domain = link_domain(url)
        if "github" in domain:
            scores["coding"] += 2
            scores["tools"] += 1
        if "arxiv" in domain:
            scores["papers"] += 3
        if "huggingface" in domain:
            scores["models"] += 2
            scores["tools"] += 1

    best = max(scores, key=scores.get)
    best_score = scores[best]
    category = best if best_score > 0 else "misc"
    total_signal = sum(scores.values()) or 1
    confidence = min(0.95, 0.35 + (best_score / total_signal) * 0.55) if best_score else 0.2

    tags = sorted({category, *top_terms(text), *domain_tags(links)})
    entities = extract_entities(text, links)
    return {
        "category": category,
        "confidence": round(confidence, 3),
        "summary": summarize(text),
        "why_it_matters": why_it_matters(text, category, links),
        "use_cases": use_cases(category),
        "entities": entities,
        "tags": tags[:12],
        "needs_review": confidence < 0.62 or category == "misc",
    }


def summarize(text: str, max_len: int = 220) -> str:
    compact = " ".join(text.split())
    if not compact:
        return "No visible tweet text captured."
    first = re.split(r"(?<=[.!?])\s+", compact)[0]
    if len(first) <= max_len:
        return first
    return first[: max_len - 1].rstrip() + "."


def why_it_matters(text: str, category: str, links: list[str] | tuple[str, ...]) -> str:
    if category == "misc":
        return "Potentially useful bookmark, but it needs manual review before it becomes durable knowledge."
    domains = sorted({link_domain(u) for u in links if link_domain(u)})
    suffix = f" Links out to {', '.join(domains[:3])}." if domains else ""
    return f"Useful for the {category.replace('-', ' ')} knowledge area because it captures a reusable idea, tool, or reference.{suffix}"


def use_cases(category: str) -> list[str]:
    defaults = {
        "ai-agents": ["Agent workflow ideas", "Browser automation patterns", "Tool-use references"],
        "coding": ["Implementation reference", "Debugging pattern", "Library evaluation"],
        "evals": ["Benchmark tracking", "Model comparison", "Quality gates"],
        "models": ["Model selection", "Inference experiments", "Capability notes"],
        "product-ideas": ["Prototype backlog", "Market research", "Feature discovery"],
        "design": ["UI inspiration", "Interaction patterns", "Design critique"],
        "infra": ["Architecture notes", "Deployment patterns", "Performance ideas"],
        "papers": ["Research reading list", "Method extraction", "Citation backlog"],
        "workflows": ["Internal playbooks", "Automation opportunities", "Process design"],
        "tools": ["Tool inventory", "Build-vs-buy comparison", "Integration ideas"],
        "prompts": ["Prompt library", "Instruction design", "Agent behavior tuning"],
        "business": ["Go-to-market notes", "Pricing ideas", "Customer research"],
        "misc": ["Manual triage"],
    }
    return defaults.get(category, defaults["misc"])


def top_terms(text: str, limit: int = 5) -> list[str]:
    stop = {"the", "and", "for", "that", "this", "with", "from", "have", "your", "you", "are", "was", "will", "can"}
    words = [w.lower() for w in WORD_RE.findall(text) if len(w) > 3 and w.lower() not in stop]
    return [word for word, _ in Counter(words).most_common(limit)]


def domain_tags(links: list[str] | tuple[str, ...]) -> list[str]:
    return [link_domain(url).split(".")[0] for url in links if link_domain(url)]


def extract_entities(text: str, links: list[str] | tuple[str, ...]) -> list[str]:
    entities = {m.group(0).strip() for m in ENTITY_RE.finditer(text)}
    entities.update(link_domain(url) for url in links if link_domain(url))
    return sorted(e for e in entities if e)[:20]


def embed_text(text: str, dims: int = 64) -> list[float]:
    vector = [0.0] * dims
    for word in WORD_RE.findall(text.lower()):
        idx = hash(word) % dims
        vector[idx] += 1.0
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [round(v / norm, 6) for v in vector]

