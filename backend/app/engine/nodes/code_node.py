from __future__ import annotations

import time
from typing import Any

from app.config import get_settings
from app.engine.context import RunContext
from app.engine.nodes.base import BaseNode, NodeOutcome
from app.engine.nodes.sandbox_runner import run_user_code

DEFAULT_CODE = '''# `payload` contient l'entrée du nœud (dict ou str).
# Assignez `result` (ou retournez une valeur depuis run(payload, context)).
text = payload.get("text") if isinstance(payload, dict) else str(payload)
words = text.split()

result = {
    "text": text.strip(),
    "word_count": len(words),
    "preview": text[:160],
}
'''


class CodeNode(BaseNode):
    type = "code"
    category = "code"
    label = "Code (Python)"
    color = "#0f766e"
    icon = "code"
    description = "Transforme les données avec un script Python exécuté dans un processus isolé."
    inputs = [{"id": "input", "label": "Entrée"}]
    outputs = [{"id": "output", "label": "Sortie"}]
    defaults = {"code": DEFAULT_CODE, "timeout": 10}

    async def run(self, inputs: dict[str, list[Any]], ctx: RunContext) -> NodeOutcome:
        code = str(self.cfg("code") or "")
        if not code.strip():
            raise ValueError("Le Code Node est vide.")
        payload = ctx.first(inputs)
        context = {
            "runId": ctx.run_id,
            "workflowId": ctx.workflow_id,
            "nodeId": self.node.id,
            "conversationId": ctx.conversation_id,
            "runInput": ctx.run_input,
        }
        started = time.perf_counter()
        result, error = await run_user_code(
            code, payload, context, timeout=float(self.cfg("timeout") or get_settings().code_node_timeout)
        )
        elapsed = (time.perf_counter() - started) * 1000
        if error:
            raise RuntimeError(error)
        return NodeOutcome(
            output=result,
            meta={"executionMs": round(elapsed, 2), "outputType": type(result).__name__},
        )
