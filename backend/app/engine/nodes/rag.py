from __future__ import annotations

import json
from typing import Any

from app.engine.context import RunContext
from app.engine.nodes.base import BaseNode, NodeOutcome
from app.services.embeddings import embed_query, embed_texts_batched
from app.services.vectorstore import VectorStore, chunk_text


def _extract_documents(payload: Any) -> list[dict[str, Any]]:
    if payload is None:
        return []
    if isinstance(payload, list):
        return [d for item in payload for d in _extract_documents(item)]
    if isinstance(payload, dict):
        if isinstance(payload.get("documents"), list):
            return payload["documents"]
        if "text" in payload and isinstance(payload["text"], str):
            return [{"id": "doc", "name": "Document", "text": payload["text"], "metadata": {}}]
    if isinstance(payload, str):
        return [{"id": "doc", "name": "Texte brut", "text": payload, "metadata": {}}]
    return [{"id": "doc", "name": "Payload", "text": json.dumps(payload, ensure_ascii=False), "metadata": {}}]


class VectorStoreNode(BaseNode):
    type = "vectorStore"
    category = "data"
    label = "Vector Store"
    color = "#8b5cf6"
    icon = "layers"
    description = "Chunking + embeddings + stockage/retrieval des documents (RAG)."
    inputs = [{"id": "input", "label": "Documents / requête"}]
    outputs = [{"id": "output", "label": "Passages"}]
    defaults = {
        "operation": "index",       # index | query
        "storeId": "default",
        "chunkSize": 800,
        "chunkOverlap": 120,
        "topK": 4,
        "reset": False,
        "query": "",
    }

    async def run(self, inputs: dict[str, list[Any]], ctx: RunContext) -> NodeOutcome:
        store = VectorStore(str(self.cfg("storeId", "default")))
        operation = str(self.cfg("operation", "index"))

        if operation == "index":
            payload = ctx.first(inputs)
            documents = _extract_documents(payload)
            chunks: list[str] = []
            metadata: list[dict[str, Any]] = []
            for doc in documents:
                text = doc.get("text", "")
                pieces = chunk_text(text, int(self.cfg("chunkSize", 800)), int(self.cfg("chunkOverlap", 120)))
                for i, piece in enumerate(pieces):
                    chunks.append(piece)
                    metadata.append(
                        {
                            "source": doc.get("source", "inline"),
                            "documentId": doc.get("id"),
                            "documentName": doc.get("name"),
                            "url": doc.get("url"),
                            "chunkIndex": i,
                            **(doc.get("metadata") or {}),
                        }
                    )
            if not chunks:
                raise ValueError("Aucun texte à indexer : connectez un nœud Source au Vector Store.")
            embeddings = await embed_texts_batched(chunks)
            total = store.add(chunks, embeddings, metadata, reset=bool(self.cfg("reset")))
            return NodeOutcome(
                output={
                    "indexed": len(chunks),
                    "documents": len(documents),
                    "storeId": store.store_id,
                    "totalVectors": total,
                    "chunks": chunks[:3],
                },
                meta={
                    "storeId": store.store_id,
                    "chunks": len(chunks),
                    "vectors": total,
                    "embeddingDim": len(embeddings[0]) if embeddings else 0,
                },
            )

        # ---- retrieval
        query = str(self.cfg("query", "") or "").strip()
        if not query:
            payload = ctx.first(inputs)
            if isinstance(payload, dict):
                query = str(payload.get("text") or payload.get("query") or "")
            elif isinstance(payload, str):
                query = payload
        if not query:
            query = ctx.prompt_text()
        if not query:
            raise ValueError("Requête vide pour le retrieval : connectez un prompt ou saisissez une requête.")

        top_k = int(self.cfg("topK", 4))
        if store.stats()["vectors"] == 0:
            raise ValueError(
                f"Le store '{store.store_id}' est vide. Exécutez d'abord un nœud Vector Store en mode 'index'."
            )
        matches = store.search(await embed_query(query), top_k=top_k)
        context = "\n\n---\n\n".join(
            f"[{m['metadata'].get('documentName') or 'doc'} · score {m['score']}]\n{m['text']}"
            for m in matches
        )
        return NodeOutcome(
            output={"query": query, "matches": matches, "context": context, "storeId": store.store_id},
            meta={
                "storeId": store.store_id,
                "matches": len(matches),
                "bestScore": matches[0]["score"] if matches else None,
                "contextChars": len(context),
            },
        )
