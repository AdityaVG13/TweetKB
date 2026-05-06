from __future__ import annotations

import math
import os
import re

WORD_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9_+-]{1,}")


def embed_text_local_hash(text: str, dims: int = 64) -> list[float]:
    """Deterministic hash-based embedding. Not semantic but fast and local."""
    vector = [0.0] * dims
    for word in WORD_RE.findall(text.lower()):
        idx = hash(word) % dims
        vector[idx] += 1.0
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [round(v / norm, 6) for v in vector]


def embed_text_ollama(text: str, model: str = "nomic-embed-text") -> list[float] | None:
    """Embed using local Ollama server. Returns None if unavailable."""
    try:
        import json
        import urllib.request

        req = urllib.request.Request(
            "http://localhost:11434/api/embeddings",
            data=json.dumps({"model": model, "prompt": text}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("embedding")
    except Exception:
        return None


def embed_text_openai(text: str, model: str = "text-embedding-3-small") -> list[float] | None:
    """Embed using OpenAI API. Returns None if unavailable or no API key."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        import json
        import urllib.request

        req = urllib.request.Request(
            "https://api.openai.com/v1/embeddings",
            data=json.dumps({"model": model, "input": text[:8192]}).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("data", [{}])[0].get("embedding")
    except Exception:
        return None


PROVIDERS = {
    "local-hash": embed_text_local_hash,
    "ollama": embed_text_ollama,
    "openai": embed_text_openai,
}


def embed_text(
    text: str,
    provider: str = "local-hash",
    model: str = "hash-v1",
    dims: int = 64,
) -> tuple[list[float], str, str]:
    """Embed text using specified provider. Returns (vector, provider, model)."""
    if provider not in PROVIDERS:
        provider = "local-hash"

    if provider == "local-hash":
        return embed_text_local_hash(text, dims), "local-hash", "hash-v1"

    if provider == "ollama":
        result = embed_text_ollama(text, model)
        if result:
            return result, "ollama", model

    if provider == "openai":
        result = embed_text_openai(text, model)
        if result:
            return result, "openai", model

    # Fallback
    return embed_text_local_hash(text, dims), "local-hash", "hash-v1"


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def embedding_dims(provider: str, model: str) -> int:
    """Return expected embedding dimensions for provider/model."""
    if provider == "openai":
        if model == "text-embedding-3-small":
            return 1536
        if model == "text-embedding-3-large":
            return 3072
        return 1536
    if provider == "ollama":
        return 768  # nomic-embed-text default
    return 64  # local-hash default
