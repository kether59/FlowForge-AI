from __future__ import annotations

import json
from typing import Any

from app.engine.context import RunContext
from app.engine.nodes.base import BaseNode, NodeOutcome


def _stringify(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("text", "answer", "output", "content", "message", "value"):
            if isinstance(value.get(key), str):
                return value[key]
    return json.dumps(value, ensure_ascii=False, default=str)


class InputNode(BaseNode):
    type = "input"
    category = "io"
    label = "Chat Input"
    color = "#0ea5e9"
    icon = "chat"
    description = "Point d'entrée : prompt utilisateur ou formulaire."
    inputs = []
    outputs = [{"id": "output", "label": "Prompt"}]
    defaults = {"field": "prompt", "placeholder": "Posez votre question…"}

    async def run(self, inputs: dict[str, list[Any]], ctx: RunContext) -> NodeOutcome:
        field = str(self.cfg("field", "prompt"))
        value = ctx.run_input.get(field)
        if value is None:
            value = ctx.prompt_text()
        text = _stringify(value)
        return NodeOutcome(
            output={
                "text": text,
                "field": field,
                "conversationId": ctx.conversation_id,
                "input": ctx.run_input,
            },
            meta={"chars": len(text)},
        )


class OutputNode(BaseNode):
    type = "output"
    category = "io"
    label = "Output"
    color = "#059669"
    icon = "flag"
    description = "Restitue la réponse finale du workflow."
    inputs = [{"id": "input", "label": "Réponse"}]
    outputs = []
    defaults = {"format": "text", "title": "Réponse finale"}

    async def run(self, inputs: dict[str, list[Any]], ctx: RunContext) -> NodeOutcome:
        payload = ctx.first(inputs)
        if payload is None:
            raise ValueError("Aucune entrée connectée au nœud Output.")
        if isinstance(payload, dict) and "text" in payload:
            text = _stringify(payload)
        else:
            text = _stringify(payload)
        result: Any = text
        if self.cfg("format") == "json":
            result = payload
        ctx.final_output = result
        return NodeOutcome(
            output={"text": text, "raw": payload, "title": self.cfg("title")},
            meta={"chars": len(text)},
        )
