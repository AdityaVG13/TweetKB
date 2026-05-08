from __future__ import annotations

import base64
import json
import os
import urllib.request
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

DEFAULT_OPENAI_VISION_MODEL = os.environ.get("TWEETKB_VISION_MODEL", "gpt-4.1-mini")
DEFAULT_OLLAMA_VISION_MODEL = os.environ.get("TWEETKB_OLLAMA_VISION_MODEL", "llava")
DEFAULT_OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")


@dataclass(frozen=True)
class ImageAnalysis:
    content_text: str
    provider: str
    model: str


def candidate_media_images(media_items: list[Any], max_media: int = 4) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    seen: set[str] = set()
    for raw in media_items:
        item = raw if isinstance(raw, dict) else {"url": str(raw or "")}
        url = str(item.get("url") or "").strip()
        alt = str(item.get("alt") or "").strip()
        if not _looks_like_content_image(url):
            continue
        if url in seen:
            continue
        seen.add(url)
        candidates.append({"url": url, "alt": alt})
        if len(candidates) >= max_media:
            break
    return candidates


def analyze_image_media(
    media: dict[str, str],
    provider: str = "openai",
    model: str | None = None,
    detail: str = "auto",
    context_text: str = "",
    timeout: float = 45.0,
) -> ImageAnalysis:
    provider = (provider or "openai").lower().strip()
    if provider == "metadata":
        return _analyze_metadata(media)
    if provider == "openai":
        return _analyze_openai(media, model or DEFAULT_OPENAI_VISION_MODEL, detail, context_text, timeout)
    if provider == "ollama":
        return _analyze_ollama(media, model or DEFAULT_OLLAMA_VISION_MODEL, context_text, timeout)
    raise ValueError(f"Unsupported vision provider: {provider}")


def _looks_like_content_image(url: str) -> bool:
    if not url.startswith(("http://", "https://")):
        return False
    parsed = urlparse(url)
    host = parsed.netloc.lower().removeprefix("www.")
    path = parsed.path.lower()
    if host in {"pbs.twimg.com", "ton.twimg.com"}:
        if "/profile_images/" in path or "/emoji/" in path:
            return False
        return "/media/" in path or "format=" in parsed.query or "name=" in parsed.query
    return path.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif"))


def _analyze_metadata(media: dict[str, str]) -> ImageAnalysis:
    alt = media.get("alt", "").strip()
    url = media.get("url", "").strip()
    if alt:
        text = f"Image alt text: {alt}\nImage URL: {url}"
    else:
        text = f"Image attached without alt text.\nImage URL: {url}"
    return ImageAnalysis(content_text=text, provider="metadata", model="alt-text")


def _analysis_prompt(media: dict[str, str], context_text: str) -> str:
    alt = media.get("alt", "").strip()
    context = " ".join((context_text or "").split())[:800]
    return "\n".join(
        [
            "Analyze this image for a private bookmark knowledge base.",
            "Describe visible objects, UI, charts, diagrams, code, screenshots, and any readable text.",
            "If text is visible, transcribe the important parts. Keep it concise but specific.",
            f"Existing alt text: {alt or '(none)'}",
            f"Bookmark context: {context or '(none)'}",
        ]
    )


def _format_result(media: dict[str, str], provider: str, model: str, text: str) -> ImageAnalysis:
    alt = media.get("alt", "").strip()
    parts = [f"Image analysis ({provider}/{model}):", text.strip()]
    if alt:
        parts.append(f"Alt text: {alt}")
    parts.append(f"Image URL: {media.get('url', '').strip()}")
    return ImageAnalysis(content_text="\n".join(parts).strip(), provider=provider, model=model)


def _analyze_openai(
    media: dict[str, str],
    model: str,
    detail: str,
    context_text: str,
    timeout: float,
) -> ImageAnalysis:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required for --vision-provider openai")
    body = {
        "model": model,
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": _analysis_prompt(media, context_text)},
                    {"type": "input_image", "image_url": media["url"], "detail": detail},
                ],
            }
        ],
        "max_output_tokens": 350,
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise RuntimeError(f"OpenAI vision request failed: {exc}") from exc
    text = _extract_openai_text(payload)
    if not text:
        raise RuntimeError("OpenAI vision response did not contain text")
    return _format_result(media, "openai", model, text)


def _extract_openai_text(payload: dict[str, Any]) -> str:
    if isinstance(payload.get("output_text"), str):
        return payload["output_text"].strip()
    chunks: list[str] = []
    for output in payload.get("output", []) or []:
        for content in output.get("content", []) or []:
            if isinstance(content.get("text"), str):
                chunks.append(content["text"])
    return "\n".join(chunks).strip()


def _analyze_ollama(media: dict[str, str], model: str, context_text: str, timeout: float) -> ImageAnalysis:
    image_bytes = _download_image(media["url"], timeout=timeout)
    body = {
        "model": model,
        "prompt": _analysis_prompt(media, context_text),
        "images": [base64.b64encode(image_bytes).decode("ascii")],
        "stream": False,
    }
    host = DEFAULT_OLLAMA_HOST.rstrip("/")
    request = urllib.request.Request(
        f"{host}/api/generate",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise RuntimeError(f"Ollama vision request failed: {exc}") from exc
    text = str(payload.get("response") or "").strip()
    if not text:
        raise RuntimeError("Ollama vision response did not contain text")
    return _format_result(media, "ollama", model, text)


def _download_image(url: str, timeout: float) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "TweetKB/0.4"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read(50 * 1024 * 1024)
