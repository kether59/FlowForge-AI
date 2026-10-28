"""Embeddings : provider OpenAI optionnel + fallback local déterministe.

Le fallback "hashing" (bag-of-words projeté sur un espace de dimension fixe,
puis normalisé) n'a aucune dépendance lourde et suffit à démontrer la chaîne
RAG complète hors ligne. Branchez `embedding_provider=openai` pour de vrais
vecteurs sémantiques.
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Iterable

import httpx

from app.config import get_settings

_TOKEN_RE = re.compile(r"[a-zà-ÿ0-9]+", re.IGNORECASE)


def _tokens(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text) if len(t) > 1]


def _bucket(token: str, dim: int) -> tuple[int, float]:
    digest = hashlib.md5(token.encode()).digest()
    idx = int.from_bytes(digest[:4], "little") % dim
    sign = 1.0 if digest[4] % 2 == 0 else -1.0
    return idx, sign


def _normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def mock_embedding(text: str, dim: int | None = None) -> list[float]:
    dim = dim or get_settings().embedding_dim
    vec = [0.0] * dim
    toks = _tokens(text)
    for i, tok in enumerate(toks):
        idx, sign = _bucket(tok, dim)
        vec[idx] += sign * (1.0 + 0.15 * min(len(tok), 8))
        # bigrammes pour capter un peu de contexte
        if i + 1 < len(toks):
            idx2, sign2 = _bucket(tok + "_" + toks[i + 1], dim)
            vec[idx2] += sign2 * 0.5
    return _normalize(vec)


async def embed_texts(texts: Iterable[str]) -> list[list[float]]:
    settings = get_settings()
    items = list(texts)
    if not items:
        return []
    if settings.embedding_provider == "openai" and settings.openai_api_key:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                settings.openai_base_url.rstrip("/") + "/embeddings",
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                json={"model": settings.embedding_model, "input": items},
            )
            resp.raise_for_status()
            data = resp.json()["data"]
            return [row["embedding"] for row in data]
    return [mock_embedding(t) for t in items]


async def embed_query(text: str) -> list[float]:
    return (await embed_texts([text]))[0]


async def embed_texts_batched(texts: Iterable[str], batch_size: int = 100) -> list[list[float]]:
    items = list(texts)
    if batch_size < 1:
        raise ValueError("batch_size doit être supérieur à zéro")
    vectors: list[list[float]] = []
    for start in range(0, len(items), batch_size):
        vectors.extend(await embed_texts(items[start : start + batch_size]))
    return vectors
