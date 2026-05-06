"""Ollama embedding calls."""
from __future__ import annotations

import httpx

from config import OLLAMA_URL, EMBED_MODEL


def embed(text: str) -> list[float]:
    """Return a float embedding vector for the given text via Ollama."""
    url = f"{OLLAMA_URL}/api/embeddings"
    response = httpx.post(url, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    response.raise_for_status()
    return response.json()["embedding"]
