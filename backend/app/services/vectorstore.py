"""Vector store minimaliste, persistant sur disque (JSON) et sans dépendance.

Suffisant pour un prototype : cosine similarity + top_k. Pour la production,
remplacez cette classe par pgvector, Qdrant, Chroma ou FAISS — l'interface
(`add`, `search`, `stats`, `clear`) est volontairement réduite.
"""

from __future__ import annotations

import json
import math
import re
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.config import DATA_DIR

VECTOR_DIR = DATA_DIR / "vectors"
VECTOR_DIR.mkdir(parents=True, exist_ok=True)


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)


def chunk_text(text: str, size: int = 800, overlap: int = 120) -> list[str]:
    """Chunking par paragraphes puis fenêtres glissantes de caractères."""
    text = re.sub(r"\r\n?", "\n", text).strip()
    if not text:
        return []
    size = max(100, int(size))
    overlap = max(0, min(int(overlap), size // 2))

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    buf = ""
    for p in paragraphs:
        if len(buf) + len(p) + 2 <= size:
            buf = f"{buf}\n\n{p}" if buf else p
            continue
        if buf:
            chunks.append(buf)
        if len(p) <= size:
            buf = p
        else:
            start = 0
            while start < len(p):
                chunks.append(p[start : start + size])
                start += size - overlap
            buf = ""
    if buf:
        chunks.append(buf)

    # fenêtres avec overlap pour les chunks trop longs
    final: list[str] = []
    for c in chunks:
        if len(c) <= size:
            final.append(c)
        else:
            start = 0
            while start < len(c):
                final.append(c[start : start + size])
                start += size - overlap
    return [c.strip() for c in final if c.strip()]


@dataclass
class VectorRecord:
    id: str
    text: str
    embedding: list[float]
    metadata: dict[str, Any]


class VectorStore:
    def __init__(self, store_id: str) -> None:
        self.store_id = re.sub(r"[^a-zA-Z0-9_-]", "_", store_id or "default")
        self.path = VECTOR_DIR / f"{self.store_id}.json"
        self._records: list[VectorRecord] = []
        self._load()

    # ------------------------------------------------------------------ io
    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            payload = json.loads(self.path.read_text())
            self._records = [
                VectorRecord(
                    id=r["id"],
                    text=r["text"],
                    embedding=r["embedding"],
                    metadata=r.get("metadata", {}),
                )
                for r in payload.get("records", [])
            ]
        except (json.JSONDecodeError, KeyError):
            self._records = []

    def _save(self, meta: dict[str, Any] | None = None) -> None:
        payload = {
            "storeId": self.store_id,
            "updatedAt": time.time(),
            "meta": meta or {},
            "records": [
                {"id": r.id, "text": r.text, "embedding": r.embedding, "metadata": r.metadata}
                for r in self._records
            ],
        }
        self.path.write_text(json.dumps(payload))

    # -------------------------------------------------------------- public
    def add(self, texts: list[str], embeddings: list[list[float]], metadata: list[dict] | None = None,
            reset: bool = False) -> int:
        if reset:
            self._records = []
        else:
            document_keys = {
                (md.get("source"), md.get("documentId"))
                for md in metadata or []
                if md.get("documentId") is not None
            }
            if document_keys:
                self._records = [
                    record
                    for record in self._records
                    if (record.metadata.get("source"), record.metadata.get("documentId"))
                    not in document_keys
                ]
        for i, (text, emb) in enumerate(zip(texts, embeddings)):
            md = metadata[i] if metadata and i < len(metadata) else {}
            self._records.append(
                VectorRecord(id=str(uuid.uuid4()), text=text, embedding=emb, metadata=md)
            )
        self._save()
        return len(self._records)

    def search(self, query_embedding: list[float], top_k: int = 4,
               min_score: float = 0.0) -> list[dict[str, Any]]:
        scored = []
        for rec in self._records:
            score = _cosine(query_embedding, rec.embedding)
            if score >= min_score:
                scored.append(
                    {
                        "id": rec.id,
                        "text": rec.text,
                        "score": round(score, 4),
                        "metadata": rec.metadata,
                    }
                )
        scored.sort(key=lambda r: r["score"], reverse=True)
        return scored[: max(1, top_k)]

    def stats(self) -> dict[str, Any]:
        return {
            "storeId": self.store_id,
            "vectors": len(self._records),
            "updatedAt": self.path.stat().st_mtime if self.path.exists() else None,
        }

    def clear(self) -> None:
        self._records = []
        self._save()

    def list_stores(self) -> list[dict[str, Any]]:
        out = []
        for p in VECTOR_DIR.glob("*.json"):
            try:
                data = json.loads(p.read_text())
                out.append(
                    {
                        "storeId": p.stem,
                        "vectors": len(data.get("records", [])),
                        "updatedAt": data.get("updatedAt"),
                    }
                )
            except json.JSONDecodeError:
                continue
        return sorted(out, key=lambda x: x["storeId"])


def list_stores() -> list[dict[str, Any]]:
    return VectorStore("__tmp").list_stores()


def store_path(store_id: str) -> Path:
    return VECTOR_DIR / f"{re.sub(r'[^a-zA-Z0-9_-]', '_', store_id)}.json"
