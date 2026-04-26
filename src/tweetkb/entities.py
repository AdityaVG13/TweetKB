from __future__ import annotations

import re
from urllib.parse import urlparse

ENTITY_TYPE_ALIASES = {
    # Models
    "gpt": "model",
    "gpt-4": "model",
    "gpt-4o": "model",
    "gpt-3.5": "model",
    "claude": "model",
    "claude-3": "model",
    "claude-3.5": "model",
    "gemini": "model",
    "llama": "model",
    "qwen": "model",
    "mistral": "model",
    "grok": "model",
    "phi": "model",
    "yi": "model",
    "deepseek": "model",
    "mixtral": "model",
    "command-r": "model",
    # Frameworks
    "browser-harness": "framework",
    "mcp": "protocol",
    "langchain": "framework",
    "llamaindex": "framework",
    "autogen": "framework",
    "crewai": "framework",
    "dspy": "framework",
    # Benchmarks
    "swe-bench": "benchmark",
    "mmlu": "benchmark",
    "humaneval": "benchmark",
    "big bench": "benchmark",
    "arc": "benchmark",
    "truthfulqa": "benchmark",
    "alpacaeval": "benchmark",
    # Databases
    "sqlite": "database",
    "postgres": "database",
    "mysql": "database",
    "redis": "database",
    "mongodb": "database",
    "dynamodb": "database",
    # Frameworks/apps
    "tauri": "framework",
    "electron": "framework",
    "react": "framework",
    "svelte": "framework",
    "vue": "framework",
    "nextjs": "framework",
    "nuxt": "framework",
    "astro": "framework",
    "vite": "tool",
    "webpack": "tool",
    "esbuild": "tool",
    "rollup": "tool",
    # Tools
    "pip": "tool",
    "uv": "tool",
    "npx": "tool",
    "npm": "tool",
    "pnpm": "tool",
    "bun": "tool",
    "cargo": "tool",
    "poetry": "tool",
    # Infrastructure
    "kubernetes": "cloud",
    "k8s": "cloud",
    "docker": "tool",
    "terraform": "tool",
    "ansible": "tool",
    # Apps
    "obsidian": "app",
    "logseq": "app",
    "roam": "app",
    "notion": "app",
    "linear": "app",
    "figma": "app",
    # Domains
    "github.com": "domain",
    "huggingface.co": "domain",
    "arxiv.org": "domain",
    "openai.com": "domain",
    "anthropic.com": "domain",
    # Companies
    "openai": "company",
    "anthropic": "company",
    "meta": "company",
    "google": "company",
    "microsoft": "company",
    "apple": "company",
    "amazon": "company",
    "nvidia": "company",
    "mistral ai": "company",
    "hugging face": "company",
}

KNOWN_ENTITIES = {
    # Models
    "GPT-4": ("model", "OpenAI's GPT-4 model"),
    "GPT-4o": ("model", "OpenAI's GPT-4o model"),
    "Claude": ("model", "Anthropic's Claude model family"),
    "Claude 3": ("model", "Anthropic's Claude 3 model family"),
    "Claude 3.5": ("model", "Anthropic's Claude 3.5 model family"),
    "Gemini": ("model", "Google's Gemini model family"),
    "Llama": ("model", "Meta's Llama open model family"),
    "Qwen": ("model", "Alibaba's Qwen model family"),
    "Mistral": ("model", "Mistral AI's model family"),
    "Grok": ("model", "xAI's Grok model"),
    "DeepSeek": ("model", "DeepSeek's model family"),
    "Mixtral": ("model", "Mistral AI's Mixtral mixture of experts"),
    "Phi": ("model", "Microsoft's Phi small language models"),
    "Command R": ("model", "Cohere's Command R model"),
    # Frameworks & Protocols
    "MCP": ("protocol", "Model Context Protocol"),
    "Browser-Harness": ("framework", "Browser automation framework"),
    "LangChain": ("framework", "LLM application framework"),
    "LangServe": ("framework", "LangChain deployment framework"),
    "LlamaIndex": ("framework", "LLM data framework"),
    "AutoGen": ("framework", "Microsoft's multi-agent framework"),
    "CrewAI": ("framework", "Multi-agent AI framework"),
    "DSPy": ("framework", "Stanford's declarative language model programming"),
    # Benchmarks
    "SWE-bench": ("benchmark", "Software engineering benchmark"),
    "MMLU": ("benchmark", "Massive Multitask Language Understanding"),
    "HumanEval": ("benchmark", "Code generation benchmark"),
    # Databases & Storage
    "SQLite": ("database", "Embedded SQL database"),
    "PostgreSQL": ("database", "Postgres relational database"),
    "Redis": ("database", "In-memory data store"),
    # Apps
    "Obsidian": ("app", "Local-first knowledge base"),
    "Logseq": ("app", "Outliner-style knowledge base"),
    "Tauri": ("framework", "Rust desktop app framework"),
    # Protocols & Standards
    "REST": ("protocol", "REST API protocol"),
    "GraphQL": ("protocol", "GraphQL query protocol"),
    "WebSocket": ("protocol", "WebSocket protocol"),
    "WebRTC": ("protocol", "Real-time communication"),
}

ENTITY_RE = re.compile(
    r"\b(?:[A-Z][A-Za-z0-9]+(?:\s+[A-Z][A-Za-z0-9]+){0,3}|"
    r"GPT-\d(?:\.\d)?|Claude-\d(?:\.\d)?|Gemini(?:\s+\d+(?:\.\d+)?)?|"
    r"Llama-\d|Llama\d|Qwen(?:\s+\d+(?:\.\d+)?)?|Mistral(?:-\d)?|"
    r"MCP|SWE-bench|MMLU|HumanEval|SWE-bench)\b"
)

HANDLE_RE = re.compile(r"@([A-Za-z0-9_]{1,15})")
URL_ENT_RE = re.compile(
    r"github\.com/([\w.-]+)/([\w.-]+)|"
    r"huggingface\.co/([\w.-]+)/([\w.-]+)|"
    r"arxiv\.org/abs/(\d+\.\d+)|"
    r"arxiv\.org/pdf/(\d+\.\d+)"
)


def extract_entities(text: str, links: list[str] | tuple[str, ...] = ()) -> list[tuple[str, str, str]]:
    """Extract entities from text and links. Returns list of (name, type, source)."""
    results: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str]] = set()

    # Text regex entities
    for match in ENTITY_RE.finditer(text):
        name = match.group(0).strip()
        if len(name) < 2:
            continue
        entity_type = detect_entity_type(name)
        key = (name.lower(), entity_type)
        if key not in seen:
            seen.add(key)
            results.append((name, entity_type, "text-regex"))

    # Link-based entities
    for url in links:
        if not url:
            continue
        domain = get_domain(url)
        if domain == "github.com":
            m = URL_ENT_RE.search(url)
            if m:
                repo = m.group(1) or m.group(2)
                if repo:
                    key = (repo.lower(), "repo")
                    if key not in seen:
                        seen.add(key)
                        results.append((repo, "repo", "url-pattern"))
        elif domain == "huggingface.co":
            m = URL_ENT_RE.search(url)
            if m and (m.group(3) or m.group(4)):
                name = m.group(3) or m.group(4)
                key = (name.lower(), "model")
                if key not in seen:
                    seen.add(key)
                    results.append((name, "model", "url-pattern"))
        elif domain == "arxiv.org":
            m = URL_ENT_RE.search(url)
            if m and (m.group(5) or m.group(6)):
                paper_id = m.group(5) or m.group(6)
                key = (f"arxiv:{paper_id}", "paper")
                if key not in seen:
                    seen.add(key)
                    results.append((f"arXiv:{paper_id}", "paper", "url-pattern"))

    return results


def detect_entity_type(name: str) -> str:
    """Detect entity type from name using known patterns."""
    lower = name.lower()

    # Check aliases
    if lower in ENTITY_TYPE_ALIASES:
        return ENTITY_TYPE_ALIASES[lower]

    # Check known entities
    if name in KNOWN_ENTITIES:
        return KNOWN_ENTITIES[name][0]

    # Heuristic patterns
    if re.match(r"^(GPT|Claude|Gemini|Llama|Qwen|Mistral|Grok|DeepSeek|Mixtral|Phi)-", name):
        return "model"
    if re.match(r"^[\w.-]+/[\w.-]+$", name):
        return "repo"
    if re.match(r"^arxiv:\d+\.\d+$", lower):
        return "paper"
    if "bench" in lower or "mmlu" in lower or lower in ("humaneval", "truthfulqa", "arc"):
        return "benchmark"
    if "api" in lower or "sdk" in lower:
        return "protocol"

    return "other"


def get_domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().removeprefix("www.")
    except Exception:
        return ""


def normalize_entity_name(name: str) -> str:
    """Normalize entity name for matching."""
    return name.lower().strip().rstrip("s")
