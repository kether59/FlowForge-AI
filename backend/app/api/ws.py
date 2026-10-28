"""Gestion des connexions WebSocket et diffusion des événements d'exécution."""

from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from typing import Any

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self._rooms: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, room: str, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._rooms[room].add(ws)

    async def disconnect(self, room: str, ws: WebSocket) -> None:
        async with self._lock:
            self._rooms[room].discard(ws)

    async def broadcast(self, room: str, event: dict[str, Any]) -> None:
        async with self._lock:
            targets = list(self._rooms[room]) + list(self._rooms.get("*", set()))
        dead: list[WebSocket] = []
        payload = json.dumps(event, default=str)
        for ws in targets:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self._rooms[room].discard(ws)

    def stats(self) -> dict[str, int]:
        return {room: len(socks) for room, socks in self._rooms.items()}


MANAGER = ConnectionManager()
