from __future__ import annotations

import os
import subprocess
import sys

from tweetkb.embeddings import embed_text, embed_text_local_hash


def test_local_hash_embedding_is_stable_across_hash_seeds():
    script = (
        "from tweetkb.embeddings import embed_text_local_hash; "
        "print(embed_text_local_hash('local sqlite knowledge base'))"
    )
    env_base = {**os.environ, "PYTHONPATH": "src"}
    first = subprocess.check_output([sys.executable, "-c", script], env={**env_base, "PYTHONHASHSEED": "1"})
    second = subprocess.check_output([sys.executable, "-c", script], env={**env_base, "PYTHONHASHSEED": "2"})

    assert first == second
    assert first.startswith(b"[")


def test_different_texts_produce_different_local_hash_vectors():
    left = embed_text_local_hash("browser harness collection")
    right = embed_text_local_hash("totally unrelated cooking recipe")

    assert left != right
    assert len(left) == 64
    assert abs(sum(v * v for v in left) - 1.0) < 1e-4


def test_embed_text_local_hash_provider_returns_named_model():
    vector, provider, model = embed_text("hello world", provider="local-hash")

    assert provider == "local-hash"
    assert model == "hash-v1"
    assert vector == embed_text_local_hash("hello world")
