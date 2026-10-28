from __future__ import annotations

import asyncio
import uuid
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

from app.api.ws import MANAGER
from app.config import get_settings
from app.engine.context import MEMORY
from app.engine.graph import GraphError, compile_graph
from app.engine.executor import GraphExecutor
from app.engine.registry import node_specs
from app.schemas import (
    ConfluenceImportRequest,
    DriveImportRequest,
    Execution,
    FlowNode,
    NodeTypeSpec,
    RunRequest,
    TestLLMRequest,
    Workflow,
    WorkflowSummary,
    utcnow,
)
from app.services import storage
from app.services.connectors import fetch_confluence_pages, fetch_drive_files
from app.services.documents import UploadTooLargeError, list_uploads, save_upload_stream
from app.services.embeddings import embed_query
from app.services.llm import LLMClient, PROVIDERS
from app.services.vectorstore import VectorStore, chunk_text, list_stores
from app.templates import all_templates

router = APIRouter()
settings = get_settings()


# --------------------------------------------------------------- catalogue
@router.get("/node-types", response_model=list[NodeTypeSpec])
async def get_node_types() -> list[dict[str, Any]]:
    return node_specs()


@router.get("/providers")
async def get_providers() -> dict[str, Any]:
    out = {}
    for key, meta in PROVIDERS.items():
        client = LLMClient(provider=key)
        out[key] = {
            "label": meta["label"],
            "models": meta["models"],
            "requiresKey": meta["requiresKey"],
            "configured": client.available,
        }
    return {"default": settings.default_provider, "providers": out}


@router.post("/providers/test")
async def test_provider(payload: TestLLMRequest) -> dict[str, Any]:
    try:
        client = LLMClient(provider=payload.provider, model=payload.model)
        result = await client.complete(
            [{"role": "user", "content": payload.prompt}], temperature=0.0, max_tokens=64
        )
        return {
            "ok": True,
            "text": result.text,
            "model": result.model,
            "promptTokens": result.prompt_tokens,
            "completionTokens": result.completion_tokens,
            "costUsd": result.cost_usd,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# --------------------------------------------------------------- workflows
@router.get("/workflows", response_model=list[WorkflowSummary])
async def get_workflows() -> list[WorkflowSummary]:
    return storage.list_workflows()


@router.post("/workflows", response_model=Workflow)
async def create_workflow(payload: dict[str, Any] | None = None) -> Workflow:
    payload = payload or {}
    workflow = Workflow(
        id=storage.new_workflow_id(),
        name=payload.get("name") or "Nouveau workflow",
        description=payload.get("description") or "",
        nodes=payload.get("nodes") or [],
        edges=payload.get("edges") or [],
    )
    return storage.save_workflow(workflow)


@router.get("/workflows/{wf_id}", response_model=Workflow)
async def get_workflow(wf_id: str) -> Workflow:
    wf = storage.get_workflow(wf_id)
    if not wf:
        raise HTTPException(404, "Workflow introuvable")
    return wf


@router.put("/workflows/{wf_id}", response_model=Workflow)
async def update_workflow(wf_id: str, workflow: Workflow) -> Workflow:
    existing = storage.get_workflow(wf_id)
    workflow.id = wf_id
    workflow.createdAt = existing.createdAt if existing else workflow.createdAt
    return storage.save_workflow(workflow)


@router.delete("/workflows/{wf_id}")
async def remove_workflow(wf_id: str) -> dict[str, bool]:
    return {"deleted": storage.delete_workflow(wf_id)}


@router.post("/workflows/{wf_id}/duplicate", response_model=Workflow)
async def duplicate_workflow(wf_id: str) -> Workflow:
    wf = storage.get_workflow(wf_id)
    if not wf:
        raise HTTPException(404, "Workflow introuvable")
    clone = wf.model_copy(deep=True)
    clone.id = storage.new_workflow_id()
    clone.name = f"{wf.name} (copie)"
    clone.createdAt = clone.updatedAt = utcnow()
    return storage.save_workflow(clone)


@router.post("/workflows/{wf_id}/validate")
async def validate_workflow(wf_id: str) -> dict[str, Any]:
    wf = storage.get_workflow(wf_id) or storage.get_workflow(wf_id)
    if not wf:
        raise HTTPException(404, "Workflow introuvable")
    try:
        graph = compile_graph(wf)
        return {
            "valid": True,
            "levels": graph.levels,
            "nodeCount": len(graph.nodes),
            "edgeCount": sum(len(v) for v in graph.incoming.values()),
        }
    except GraphError as exc:
        return {"valid": False, "error": str(exc)}


@router.post("/workflows/validate")
async def validate_payload(workflow: Workflow) -> dict[str, Any]:
    try:
        graph = compile_graph(workflow)
        return {"valid": True, "levels": graph.levels, "nodeCount": len(graph.nodes)}
    except GraphError as exc:
        return {"valid": False, "error": str(exc)}


# -------------------------------------------------------------- executions
@router.post("/workflows/{wf_id}/run", response_model=Execution)
async def run_workflow(wf_id: str, payload: RunRequest) -> Execution:
    wf = storage.get_workflow(wf_id)
    if not wf:
        raise HTTPException(404, "Workflow introuvable")
    if not wf.nodes:
        raise HTTPException(400, "Workflow vide : ajoutez au moins un nœud.")

    run_input = payload.input or {}
    if not run_input.get("prompt"):
        run_input["prompt"] = ""

    async def emitter(event: dict[str, Any]) -> None:
        await MANAGER.broadcast(f"workflow:{wf_id}", event)
        if event.get("runId"):
            await MANAGER.broadcast(f"run:{event['runId']}", event)

    executor = GraphExecutor(emitter=emitter)
    try:
        execution = await executor.run(
            wf,
            run_input=run_input,
            conversation_id=payload.conversationId,
            provider=payload.provider,
            model=payload.model,
        )
    except GraphError as exc:
        raise HTTPException(400, f"Graphe invalide: {exc}") from exc
    storage.save_execution(execution)
    await MANAGER.broadcast(
        f"workflow:{wf_id}", {"type": "run.finished", "runId": execution.id, "data": execution.model_dump()}
    )
    return execution


@router.get("/executions", response_model=list[dict[str, Any]])
async def get_executions(workflowId: str | None = None, limit: int = 30) -> list[dict[str, Any]]:
    return storage.list_executions(workflowId, limit)


@router.get("/executions/{run_id}", response_model=Execution)
async def get_execution(run_id: str) -> Execution:
    execution = storage.get_execution(run_id)
    if not execution:
        raise HTTPException(404, "Exécution introuvable")
    return execution


@router.delete("/conversations/{conversation_id}")
async def clear_conversation(conversation_id: str) -> dict[str, bool]:
    await MEMORY.clear(conversation_id)
    return {"cleared": True}


# ------------------------------------------------------------------ sources
@router.post("/sources/upload")
async def upload_source(file: UploadFile = File(...)) -> dict[str, Any]:
    max_upload_bytes = max(1, settings.max_upload_size_mb) * 1024 * 1024
    try:
        file.file.seek(0)
        doc = await run_in_threadpool(
            save_upload_stream,
            file.filename or "document.txt",
            file.file,
            max_upload_bytes,
        )
    except UploadTooLargeError as exc:
        raise HTTPException(413, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(422, f"Impossible d'extraire le texte: {exc}") from exc
    return {"document": doc.model_dump(), "preview": doc.text[:1200], "chars": len(doc.text)}


@router.get("/sources/uploads")
async def get_uploads() -> list[dict[str, Any]]:
    return list_uploads()


@router.post("/sources/drive")
async def import_drive(payload: DriveImportRequest) -> dict[str, Any]:
    docs, info = await asyncio.to_thread(
        fetch_drive_files,
        payload.folderId,
        payload.fileIds,
        payload.credentialsPath,
        payload.limit,
    )
    return {"mode": info, "documents": [d.model_dump() for d in docs]}


@router.post("/sources/confluence")
async def import_confluence(payload: ConfluenceImportRequest) -> dict[str, Any]:
    docs, info = await asyncio.to_thread(
        fetch_confluence_pages,
        None,
        None,
        None,
        payload.pageId,
        payload.spaceKey,
        payload.cql,
        payload.limit,
    )
    return {"mode": info, "documents": [d.model_dump() for d in docs]}


# ------------------------------------------------------------- vector store
@router.get("/vectorstores")
async def get_vectorstores() -> list[dict[str, Any]]:
    return list_stores()


@router.get("/vectorstores/{store_id}")
async def get_vectorstore(store_id: str, topK: int = 4, q: str | None = None) -> dict[str, Any]:
    store = VectorStore(store_id)
    stats = store.stats()
    if q:
        stats["matches"] = store.search(await embed_query(q), top_k=topK)
    return stats


@router.post("/vectorstores/{store_id}/index")
async def index_to_store(store_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    from app.services.embeddings import embed_texts_batched

    text = payload.get("text") or ""
    if not text.strip():
        raise HTTPException(400, "Aucun texte fourni")
    chunks = chunk_text(text, int(payload.get("chunkSize", 800)), int(payload.get("chunkOverlap", 120)))
    embeddings = await embed_texts_batched(chunks)
    total = VectorStore(store_id).add(
        chunks, embeddings, [{"documentName": payload.get("name", "document")} for _ in chunks]
    )
    return {"storeId": store_id, "chunks": len(chunks), "totalVectors": total}


@router.delete("/vectorstores/{store_id}")
async def clear_vectorstore(store_id: str) -> dict[str, Any]:
    store = VectorStore(store_id)
    store.clear()
    return {"cleared": True, **store.stats()}
