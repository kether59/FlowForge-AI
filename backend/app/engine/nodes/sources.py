from __future__ import annotations

from typing import Any

from app.engine.context import RunContext
from app.engine.nodes.base import BaseNode, NodeOutcome
from app.schemas import SourceDocument
from app.services.connectors import fetch_confluence_pages, fetch_drive_files
from app.services.documents import load_uploaded

DEMO_INLINE = (
    "FlowForge est une plateforme d'orchestration de processus IA en drag-and-drop. "
    "Elle permet de connecter des sources documentaires, un vector store, des modèles de "
    "langage et de la logique conditionnelle dans un graphe exécutable. Chaque exécution "
    "est monitorée en temps réel : latence, tokens consommés et coût estimé par nœud.\n\n"
    "Le moteur traduit le graphe visuel en DAG, exécute les nœuds en parallèle par niveau "
    "et diffuse les tokens du LLM via WebSocket."
)


class SourceNode(BaseNode):
    type = "source"
    category = "data"
    label = "Source"
    color = "#f59e0b"
    icon = "database"
    description = "Ingère des documents : upload PDF/TXT, Google Drive ou Confluence."
    inputs = []
    outputs = [{"id": "output", "label": "Documents"}]
    defaults = {
        "kind": "inline",       # inline | upload | drive | confluence
        "text": DEMO_INLINE,
        "fileIds": [],
        "driveFolderId": "",
        "confluenceSpaceKey": "DEMO",
        "confluencePageId": "",
        "limit": 10,
    }

    async def run(self, inputs: dict[str, list[Any]], ctx: RunContext) -> NodeOutcome:
        kind = str(self.cfg("kind", "inline"))
        docs: list[SourceDocument] = []
        meta: dict[str, Any] = {"kind": kind}

        if kind == "upload":
            for file_id in self.cfg("fileIds", []) or []:
                doc = load_uploaded(str(file_id))
                if doc:
                    docs.append(doc)
            if not docs:
                meta["warning"] = "Aucun fichier uploadé trouvé (fileIds vide ou introuvable)."
        elif kind == "drive":
            docs, info = fetch_drive_files(
                folder_id=self.cfg("driveFolderId") or None,
                file_ids=self.cfg("fileIds", []) or None,
                limit=int(self.cfg("limit", 10)),
            )
            meta.update(info)
        elif kind == "confluence":
            docs, info = fetch_confluence_pages(
                page_id=self.cfg("confluencePageId") or None,
                space_key=self.cfg("confluenceSpaceKey") or None,
                limit=int(self.cfg("limit", 10)),
            )
            meta.update(info)
        else:
            text = str(self.cfg("text", ""))
            if text.strip():
                docs = [
                    SourceDocument(
                        id="inline-1",
                        name="Document inline",
                        text=text,
                        source="inline",
                    )
                ]

        meta["documents"] = len(docs)
        meta["chars"] = sum(len(d.text) for d in docs)
        return NodeOutcome(
            output={"documents": [d.model_dump() for d in docs], "count": len(docs)},
            meta=meta,
        )
