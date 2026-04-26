from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

CATEGORIES = (
    "ai-agents",
    "coding",
    "evals",
    "models",
    "product-ideas",
    "design",
    "infra",
    "papers",
    "workflows",
    "tools",
    "prompts",
    "business",
    "security",
    "data",
    "robotics",
    "voice-audio",
    "vision",
    "browser-automation",
    "local-first",
    "open-source",
    "misc",
)

CATEGORY_LABELS = {
    "ai-agents": "AI Agents",
    "coding": "Coding",
    "evals": "Evals",
    "models": "Models",
    "product-ideas": "Product Ideas",
    "design": "Design",
    "infra": "Infra",
    "papers": "Papers",
    "workflows": "Workflows",
    "tools": "Tools",
    "prompts": "Prompts",
    "business": "Business",
    "security": "Security",
    "data": "Data",
    "robotics": "Robotics",
    "voice-audio": "Voice/Audio",
    "vision": "Vision",
    "browser-automation": "Browser Automation",
    "local-first": "Local-First",
    "open-source": "Open Source",
    "misc": "Misc",
}

KEYWORDS = {
    "ai-agents": (
        "agent", "agents", "browser agent", "computer use", "automation", "tool use", "mcp",
        "autonomous", "agentic", "multi-agent", "agent loop", "plan and execute",
        "browser-harness", "playwright", "selenium", "puppeteer",
    ),
    "coding": (
        "code", "coding", "repo", "github", "typescript", "python", "rust", "debug", "test",
        "compiler", "linter", "formatter", "ide", "vscode", "neovim", "debugger",
        "algorithm", "data structure", "api", "library", "package", "npm", "pip", "cargo",
    ),
    "evals": (
        "eval", "evaluation", "benchmark", "score", "leaderboard", "swe-bench", "accuracy",
        "metric", "humaneval", "mmlu", "truthfulqa", "arc", "big bench", "helicopter",
        "measurement", "testing llm", "red teaming", "adversarial",
    ),
    "models": (
        "model", "llm", "gpt", "claude", "gemini", "llama", "qwen", "mistral", "inference",
        "gpt-4", "gpt-4o", "claude-3", "gemini-pro", "mixtral", "phi", "yi", "deepseek",
        "model release", "model card", "weights", "quantization", "fine-tune", "rag",
    ),
    "product-ideas": (
        "idea", "startup", "product", "saas", "build", "ship", "workflow", "pain point",
        "mvp", "launch", "bootstrapped", "side project", "indie hacker", "pricing",
        "go-to-market", "gtm", "customer development",
    ),
    "design": (
        "design", "ux", "ui", "interface", "figma", "visual", "layout", "brand", "typography",
        "color", "icon", "illustration", "css", "tailwind", "component library", "design system",
        "user experience", "accessibility", "a11y",
    ),
    "infra": (
        "infra", "server", "database", "sqlite", "postgres", "mysql", "redis", "queue",
        "deploy", "kubernetes", "k8s", "docker", "container", "microservice", "api gateway",
        "load balancer", "cdn", "cloud", "aws", "gcp", "azure", "vercel", "netlify",
        "latency", "throughput", "scalability", "reliability",
    ),
    "papers": (
        "paper", "arxiv", "research", "study", "publication", "abstract", "method",
        "submission", "conference", "journal", " preprint", "arxiv.org", "iclr", "neurips",
        "icml", " ACL", "EMNLP", "findings", "novel",
    ),
    "workflows": (
        "workflow", "process", "ops", "checklist", "playbook", "system", "habit",
        "automation", "zapier", "make", "n8n", "cron", "schedule", "pipeline",
        "ci/cd", "github actions", "gitlab ci", "deployment",
    ),
    "tools": (
        "tool", "library", "framework", "app", "extension", "cli", "sdk", "api",
        "utility", "software", "platform", "saas tool", "open source tool", "dev tool",
        "productivity", "boilerplate", "starter", "template",
    ),
    "prompts": (
        "prompt", "prompting", "system prompt", "instructions", "context", "few-shot",
        "chain of thought", "cot", "zero-shot", "one-shot", "multi-shot", "prompt engineering",
        "prompt tuning", "soft prompt",
    ),
    "business": (
        "business", "sales", "marketing", "pricing", "gtm", "customer", "revenue", "market",
        "b2b", "b2c", "saas", "arr", "mrr", "churn", "ltv", "cac", "growth",
        "strategy", "competition", "moat", "differentiation",
    ),
    "security": (
        "security", "cve", "vulnerability", "exploit", "breach", "attack", "pentest",
        "bug bounty", "owasp", "xss", "sql injection", "authentication", "authorization",
        "encryption", "zero-day", "patch",
    ),
    "data": (
        "dataset", "data engineering", "analytics", "analytics", "etl", "pipeline",
        "data warehouse", "snowflake", "bigquery", "databricks", "spark", "hadoop",
        "data lake", "data mesh", "data quality", "data governance",
    ),
    "robotics": (
        "robot", "robotics", "hardware", "actuator", "sensor", "lidar", "radar",
        "autonomous vehicle", "drone", "manipulator", "control", "planner",
        "reinforcement learning", "sim-to-real",
    ),
    "voice-audio": (
        "speech", "tts", "stt", "voice", "audio", "asr", "text to speech",
        "speech recognition", "music generation", "sound", "whisper", "elevenlabs",
    ),
    "vision": (
        "vision", "image", "video", "ocr", "detection", "segmentation",
        "diffusion", "stable diffusion", "midjourney", "dall-e", "generative image",
        "video generation", "sora", "runway", "computer vision",
    ),
    "browser-automation": (
        "browser automation", "web scraping", "dom", "crawl", "scraper", "selenium",
        "playwright", "puppeteer", "crawling", "scraping", "html parsing",
    ),
    "local-first": (
        "local-first", "offline", "sync", "conflict-free", "crdt", "operational transform",
        "local storage", "p2p", "peer-to-peer", "distributed",
    ),
    "open-source": (
        "open source", "oss", "github", "license", "mit license", "apache", "gpl",
        "contributor", "maintainer", "community", "fork", "star", "pull request",
    ),
}

DOMAIN_CATEGORY_BOOSTS = {
    "github.com": {"coding": 3, "tools": 2, "open-source": 2},
    "arxiv.org": {"papers": 4, "models": 2, "evals": 1},
    "huggingface.co": {"models": 3, "tools": 2, "papers": 1},
    "github.com/transformers": {"models": 2, "coding": 1},
    "github.com/llama": {"models": 2},
    "github.com/gpt": {"models": 2},
    "youtube.com": {"video": 1},
    "twitter.com": {"misc": -1},
    "x.com": {"misc": -1},
}

WORD_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9_+-]{1,}")
ENTITY_RE = re.compile(
    r"\b(?:[A-Z][A-Za-z0-9]+(?:\s+[A-Z][A-Za-z0-9]+){0,3}|"
    r"GPT-\d(?:\.\d)?|Claude|Gemini|Llama|Qwen|MCP|API|SDK|WANDr?|CLI)\b"
)


def classify_text(text: str, links: list[str] | tuple[str, ...] = ()) -> dict[str, Any]:
    lower = text.lower()
    scores: dict[str, float] = {cat: 0.0 for cat in CATEGORIES}
    signals: dict[str, list[str]] = {cat: [] for cat in CATEGORIES}

    # Keyword matching
    for cat, words in KEYWORDS.items():
        for word in words:
            if word in lower:
                weight = 2.0 if " " in word else 1.0
                scores[cat] += weight
                signals[cat].append(f"keyword:{word}")

    # URL/domain matching
    for url in links:
        domain = link_domain(url)
        if domain in DOMAIN_CATEGORY_BOOSTS:
            for cat, boost in DOMAIN_CATEGORY_BOOSTS[domain].items():
                scores[cat] += boost
                signals[cat].append(f"domain:{domain}")

    # Repo detection
    if "/repo/" in str(links) or re.search(r"github\.com/[\w-]+/[\w.-]+", str(links)):
        scores["coding"] += 2.0
        scores["open-source"] += 1.5
        signals["coding"].append("github-repo")
        signals["open-source"].append("github-repo")

    # arXiv paper detection
    if "arxiv.org" in str(links):
        scores["papers"] += 3.0
        signals["papers"].append("arxiv-link")

    # Model/tool/repo extraction from URLs
    repo_match = re.search(r"github\.com/([\w-]+)/([\w.-]+)", str(links))
    if repo_match:
        scores["coding"] += 1.0
        signals["coding"].append(f"repo:{repo_match.group(2)}")

    # Sort by score
    sorted_cats = sorted(scores.items(), key=lambda x: -x[1])
    top_cats = [(cat, score) for cat, score in sorted_cats if score > 0]

    # Build multi-label result
    categories = []
    for cat, score in top_cats[:5]:
        rationales = signals.get(cat, [])
        total_signal = sum(s for _, s in top_cats) or 1
        confidence = min(0.95, 0.3 + (score / total_signal) * 0.65)
        categories.append({
            "slug": cat,
            "confidence": round(confidence, 3),
            "method": "keyword+url",
            "rationale": "; ".join(rationales[:3]) if rationales else "matched category keywords",
        })

    primary = categories[0]["slug"] if categories else "misc"
    primary_conf = categories[0]["confidence"] if categories else 0.1

    tags = sorted({primary, *top_terms(text), *domain_tags(links)})
    entities = extract_entities(text, links)

    needs_review = (
        primary == "misc"
        or primary_conf < 0.45
        or len([c for c in categories if c["confidence"] > 0.4]) == 0
    )

    return {
        "primary": primary,
        "categories": categories,
        "confidence": primary_conf,
        "tags": tags[:12],
        "entities": entities,
        "needs_review": needs_review,
        "summary": summarize(text),
        "why_it_matters": why_it_matters(text, primary, links),
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
    stop = {
        "the", "and", "for", "that", "this", "with", "from", "have", "your",
        "you", "are", "was", "will", "can", "not", "but", "its", "has",
        "all", "was", "were", "been", "being", "what", "when", "where",
        "which", "who", "how", "only", "also", "just", "more", "than",
        "into", "out", "over", "under", "after", "before", "between",
    }
    words = [w.lower() for w in WORD_RE.findall(text) if len(w) > 3 and w.lower() not in stop]
    return [word for word, _ in Counter(words).most_common(limit)]


def domain_tags(links: list[str] | tuple[str, ...]) -> list[str]:
    return [link_domain(url).split(".")[0] for url in links if link_domain(url)]


def link_domain(url: str) -> str:
    try:
        from urllib.parse import urlparse
        return urlparse(url).netloc.lower().removeprefix("www.")
    except Exception:
        return ""


def extract_entities(text: str, links: list[str] | tuple[str, ...] = ()) -> list[str]:
    entities = {m.group(0).strip() for m in ENTITY_RE.finditer(text)}
    for url in links:
        domain = link_domain(url)
        if domain:
            entities.add(domain.split(".")[0])
    return sorted(e for e in entities if e)[:20]


def embed_text(text: str, dims: int = 64) -> list[float]:
    vector = [0.0] * dims
    for word in WORD_RE.findall(text.lower()):
        idx = hash(word) % dims
        vector[idx] += 1.0
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [round(v / norm, 6) for v in vector]
