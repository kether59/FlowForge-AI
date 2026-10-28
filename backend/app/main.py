"""FlowForge AI — API FastAPI.

Démarrage :
    uvicorn app.main:app --reload --port 8000
"""

from __future__ import annotations

import json

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.api.ws import MANAGER
from app.config import get_settings
from app.engine.graph import GraphError
from app.engine.registry import node_specs
from app.schemas import Workflow
from app.engine.executor import GraphExecutor, ExecutionError
from app.services import storage
from app.templates import all_templates

settings = get_settings()

app = FastAPI(
    title="FlowForge AI",
    version="0.1.0",
    description="Orchestrateur de workflows IA en drag-and-drop (LLM, RAG, logique conditionnelle).",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def seed_templates() -> None:
    """Crée les workflows de démonstration au premier lancement."""
    if storage.list_workflows():
        return
    for wf in all_templates():
        storage.save_workflow(wf)


@app.get("/api/health")
async def health() -> dict:
    from app.services.llm import LLMClient

    client = LLMClient()
    return {
        "status": "ok",
        "app": settings.app_name,
        "defaultProvider": client.provider,
        "providerConfigured": client.available,
        "nodeTypes": len(node_specs()),
        "wsClients": MANAGER.stats(),
    }


app.include_router(router, prefix="/api")


# ------------------------------------------------------------------ WebSockets
@app.websocket("/ws/workflows/{wf_id}")
async def ws_workflow(ws: WebSocket, wf_id: str) -> None:
    """Canal d'exécution : envoie un JSON {action: run, input, conversationId} ou Start."""
    room = f"workflow:{wf_id}"
    await MANAGER.connect(room, ws)
    try:
        await ws.send_text(json.dumps({"type": "connected", "room": room}))
        while True:
            raw = await ws.receive_text()
            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_text(json.dumps({"type": "error", "error": "JSON invalide"}))
                continue
            if message.get("action") != "run":
                continue
            workflow = storage.get_workflow(wf_id)
            if not workflow:
                await ws.send_text(json.dumps({"type": "error", "error": "Workflow introuvable"}))
                continue

            async def emitter(event: dict) -> None:
                if event.get("runId"):
                    await MANAGER.broadcast(f"run:{event['runId']}", event)
                await ws.send_text(json.dumps(event, default=str))

            executor = GraphExecutor(emitter=emitter)
            try:
                execution = await executor.run(
                    workflow,
                    run_input=message.get("input") or {},
                    conversation_id=message.get("conversationId"),
                    provider=message.get("provider"),
                    model=message.get("model"),
                )
                storage.save_execution(execution)
            except (GraphError, ExecutionError) as exc:
                await ws.send_text(json.dumps({"type": "error", "runId": None, "error": str(exc)}))
            except Exception as exc:  # pragma: no cover
                await ws.send_text(json.dumps({"type": "error", "error": f"{type(exc).__name__}: {exc}"}))
    except WebSocketDisconnect:
        pass
    finally:
        await MANAGER.disconnect(room, ws)


@app.websocket("/ws/runs/{run_id}")
async def ws_run(ws: WebSocket, run_id: str) -> None:
    """Canal d'observation d'une exécution déjà lancée (monitoring/debug)."""
    room = f"run:{run_id}"
    await MANAGER.connect(room, ws)
    try:
        execution = storage.get_execution(run_id)
        if execution:
            await ws.send_text(json.dumps({"type": "run.state", "data": execution.model_dump()}, default=str))
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await MANAGER.disconnect(room, ws)
