from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque
from typing import Any, Awaitable, Callable


class ConversationMemory:
    """Mémoire conversationnelle en RAM, fenêtrée par conversation."""

    def __init__(self) -> None:
        self._store: dict[str, deque[dict[str, str]]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def get(self, conversation_id: str, window: int = 6) -> list[dict[str, str]]:
        async with self._lock:
            hist = list(self._store.get(conversation_id, deque()))
        # window = nombre de *messages* (user+assistant) conservés
        return hist[-window * 2 :] if window > 0 else []

    async def append(self, conversation_id: str, role: str, content: str, max_messages: int = 40) -> None:
        async with self._lock:
            hist = self._store[conversation_id]
            hist.append({"role": role, "content": content})
            while len(hist) > max_messages:
                hist.popleft()

    async def clear(self, conversation_id: str) -> None:
        async with self._lock:
            self._store.pop(conversation_id, None)


MEMORY = ConversationMemory()


class RunContext:
    """Contexte partagé par tous les nœuds d'une même exécution."""

    def __init__(
        self,
        run_id: str,
        workflow_id: str,
        run_input: dict[str, Any],
        conversation_id: str,
        provider: str | None = None,
        model: str | None = None,
    ) -> None:
        self.run_id = run_id
        self.workflow_id = workflow_id
        self.run_input = run_input
        self.conversation_id = conversation_id
        self.provider_override = provider
        self.model_override = model
        self.started = time.perf_counter()
        self._emitter: Callable[[dict[str, Any]], Awaitable[None]] | None = None
        self.final_output: Any = None

    def bind_emitter(self, emitter: Callable[[dict[str, Any]], Awaitable[None]]) -> None:
        self._emitter = emitter

    async def emit(self, event: dict[str, Any]) -> None:
        if not self._emitter:
            return
        event.setdefault("runId", self.run_id)
        event.setdefault("ts", time.time())
        await self._emitter(event)

    async def emit_token(self, node_id: str, token: str) -> None:
        await self.emit({"type": "node.token", "nodeId": node_id, "data": {"token": token}})

    # ------------------------------------------------------------- helpers
    @staticmethod
    def flatten(inputs: dict[str, list[Any]]) -> list[Any]:
        return [item for values in inputs.values() for item in values]

    @staticmethod
    def first(inputs: dict[str, list[Any]], *handles: str) -> Any:
        for handle in handles:
            values = inputs.get(handle)
            if values:
                return values[0]
        for values in inputs.values():
            if values:
                return values[0]
        return None

    def prompt_text(self) -> str:
        for key in ("prompt", "text", "query", "message", "input"):
            value = self.run_input.get(key)
            if isinstance(value, str) and value.strip():
                return value
        return ""
