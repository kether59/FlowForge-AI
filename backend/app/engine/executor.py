"""Moteur d'exécution de graphe asynchrone.

Pipeline : JSON React Flow -> CompiledGraph (DAG) -> exécution niveau par niveau
(parallélisme intra-niveau) -> événements WebSocket (statuts, latences, tokens).
"""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any, Awaitable, Callable

from app.engine.context import RunContext
from app.engine.graph import compile_graph
from app.engine.nodes.logic import NodeSkipped
from app.engine.registry import NODE_CLASSES, build_node
from app.schemas import Execution, NodeStatus, NodeUsage, Workflow, utcnow

Emitter = Callable[[dict[str, Any]], Awaitable[None]]


class ExecutionError(RuntimeError):
    pass


class GraphExecutor:
    def __init__(self, emitter: Emitter | None = None) -> None:
        self.emitter = emitter
        self.execution: Execution | None = None
        self._usage: dict[str, NodeUsage] = {}

    # ------------------------------------------------------------------ utils
    async def _emit(self, event: dict[str, Any]) -> None:
        if self.emitter:
            await self.emitter(event)

    def _snapshot(self) -> dict[str, Any]:
        assert self.execution is not None
        return self.execution.model_dump()

    def _edge_payload(self, node_id: str) -> Any:
        return self._usage[node_id].output

    # ------------------------------------------------------------------- run
    async def run(
        self,
        workflow: Workflow,
        *,
        run_input: dict[str, Any],
        conversation_id: str | None = None,
        provider: str | None = None,
        model: str | None = None,
    ) -> Execution:
        graph = compile_graph(workflow)  # lève GraphError si invalide
        run_id = "run_" + uuid.uuid4().hex[:12]
        conversation_id = conversation_id or f"conv_{workflow.id}"

        execution = Execution(
            id=run_id,
            workflowId=workflow.id,
            workflowName=workflow.name,
            status=NodeStatus.queued,
            trigger={"input": run_input, "conversationId": conversation_id},
        )
        execution.nodes = [
            NodeUsage(nodeId=n.id, nodeType=n.type, label=n.label or n.type) for n in workflow.nodes
        ]
        self.execution = execution
        self._usage = {u.nodeId: u for u in execution.nodes}

        ctx = RunContext(
            run_id=run_id,
            workflow_id=workflow.id,
            run_input=run_input,
            conversation_id=conversation_id,
            provider=provider,
            model=model,
        )
        ctx.bind_emitter(self._emit)

        started = time.perf_counter()
        await self._emit({"type": "run.started", "data": self._snapshot()})

        payloads: dict[str, dict[str, list[Any]]] = {nid: {} for nid in graph.nodes}
        active_edges: list[str] = []
        skipped: set[str] = set()

        try:
            for level in graph.levels:
                runnable: list[str] = []
                for nid in level:
                    usage = self._usage[nid]
                    upstream = graph.incoming[nid]
                    if not upstream or self._should_fire(nid, graph, payloads[nid]):
                        usage.status = NodeStatus.queued
                        runnable.append(nid)
                    else:
                        usage.status = NodeStatus.skipped
                        usage.error = "Branche non empruntée (condition/porte logique en amont)."
                        usage.startedAt = usage.finishedAt = utcnow()
                        usage.latencyMs = 0.0
                        skipped.add(nid)
                        await self._emit(
                            {"type": "node.finished", "nodeId": nid, "data": usage.model_dump()}
                        )

                if runnable:
                    execution.status = NodeStatus.running
                    results = await asyncio.gather(
                        *[
                            self._run_node(
                                graph.nodes[nid], payloads[nid].copy(), ctx, graph
                            )
                            for nid in runnable
                        ],
                        return_exceptions=True,
                    )
                    for nid, result in zip(runnable, results):
                        if isinstance(result, BaseException):
                            raise result  # type: ignore[misc]
                        outcome, new_edges = result  # type: ignore[misc]
                        active_edges.extend(new_edges)
                        if outcome is not None:
                            for edge in graph.outgoing[nid]:
                                if outcome.active_handles is None or edge.sourceHandle in (
                                    outcome.active_handles + [None, "output"]
                                ):
                                    payloads[edge.target].setdefault(edge.targetHandle or "input", []).append(
                                        outcome.output
                                    )
                                    await self._emit(
                                        {
                                            "type": "edge.active",
                                            "data": {"edgeId": edge.id, "source": nid, "target": edge.target},
                                        }
                                    )

            # Nœuds jamais atteints (graphe déconnecté)
            for nid, usage in self._usage.items():
                if usage.status in (NodeStatus.idle, NodeStatus.queued):
                    usage.status = NodeStatus.skipped
                    usage.error = "Nœud non atteint (aucune entrée propagée)."
                    usage.finishedAt = utcnow()
                    usage.latencyMs = 0.0

            execution.status = NodeStatus.success
        except NodeSkipped as exc:
            execution.status = NodeStatus.success
            execution.error = None
            self._finalize_skipped(str(exc))
        except Exception as exc:
            execution.status = NodeStatus.error
            execution.error = str(exc)
            for usage in self._usage.values():
                if usage.status in (NodeStatus.idle, NodeStatus.queued):
                    usage.status = NodeStatus.skipped
                    usage.error = "Annulé suite à une erreur en amont."
                    usage.finishedAt = utcnow()
        finally:
            execution.finishedAt = utcnow()
            execution.durationMs = round((time.perf_counter() - started) * 1000, 2)
            execution.nodes = list(self._usage.values())
            execution.tokens = sum(u.totalTokens for u in execution.nodes)
            execution.costUsd = round(sum(u.costUsd for u in execution.nodes), 6)
            if ctx.final_output is not None:
                execution.finalOutput = ctx.final_output
            elif execution.status is NodeStatus.success:
                outputs = [
                    u.output
                    for u in execution.nodes
                    if u.nodeType == "output" and u.status is NodeStatus.success
                ]
                if outputs:
                    execution.finalOutput = outputs[-1]
            await self._emit(
                {
                    "type": "run.finished" if execution.status is NodeStatus.success else "run.failed",
                    "data": self._snapshot(),
                }
            )
        return execution

    @staticmethod
    def _should_fire(node_id: str, graph, received: dict[str, list[Any]]) -> bool:
        """Un nœud s'exécute si au moins un de ses handles déclencheurs a reçu une donnée.

        Les handles déclencheurs non câblés sont ignorés (fallback sur "toute entrée").
        """
        node = graph.nodes[node_id]
        cls = NODE_CLASSES.get(node.type)
        triggers = getattr(cls, "trigger_handles", None) if cls else None
        if not triggers:
            return bool(received)
        wired = {
            e.targetHandle
            for e in graph.incoming.get(node_id, [])
            if e.targetHandle in triggers
        }
        if not wired:
            return bool(received)
        return any(received.get(handle) for handle in wired)

    def _finalize_skipped(self, reason: str) -> None:
        for usage in self._usage.values():
            if usage.status in (NodeStatus.idle, NodeStatus.queued):
                usage.status = NodeStatus.skipped
                usage.error = reason
                usage.finishedAt = utcnow()
                usage.latencyMs = 0.0

    # ------------------------------------------------------------- node exec
    async def _run_node(self, node, inputs, ctx: RunContext, graph) -> tuple[Any, list[str]]:
        usage = self._usage[node.id]
        usage.status = NodeStatus.running
        usage.startedAt = utcnow()
        usage.input = {k: v for k, v in inputs.items()}
        await self._emit({"type": "node.started", "nodeId": node.id, "data": usage.model_dump()})

        started = time.perf_counter()
        try:
            instance = build_node(node)
            outcome = await instance.run(inputs, ctx)
            usage.output = outcome.output
            usage.promptTokens = outcome.prompt_tokens
            usage.completionTokens = outcome.completion_tokens
            usage.totalTokens = outcome.prompt_tokens + outcome.completion_tokens
            usage.costUsd = outcome.cost_usd
            usage.meta = outcome.meta
            usage.status = NodeStatus.success
            return outcome, []
        except NodeSkipped as exc:
            usage.status = NodeStatus.skipped
            usage.error = str(exc)
            usage.output = {"skipped": True, "reason": str(exc)}
            await self._emit({"type": "node.finished", "nodeId": node.id, "data": usage.model_dump()})
            return None, []
        except Exception as exc:
            usage.status = NodeStatus.error
            usage.error = f"{type(exc).__name__}: {exc}"
            await self._emit({"type": "node.finished", "nodeId": node.id, "data": usage.model_dump()})
            raise ExecutionError(f"Nœud '{usage.label}' ({node.id}) en échec — {usage.error}") from exc
        finally:
            usage.finishedAt = utcnow()
            usage.latencyMs = round((time.perf_counter() - started) * 1000, 2)
            if usage.status is NodeStatus.success:
                await self._emit({"type": "node.finished", "nodeId": node.id, "data": usage.model_dump()})
