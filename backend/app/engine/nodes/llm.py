from __future__ import annotations

import json
from typing import Any

from app.engine.context import MEMORY, RunContext
from app.engine.nodes.base import BaseNode, NodeOutcome
from app.services.llm import LLMClient, LLMError, compute_cost

DEFAULT_SYSTEM = (
    "Tu es un assistant d'entreprise précis et concis. "
    "Réponds en français. Si des extraits documentaires sont fournis, appuie-toi "
    "uniquement sur eux et cite la source entre crochets. Si l'information est absente "
    "du contexte, dis-le explicitement au lieu d'inventer."
)


def _text_of(payload: Any) -> str:
    if payload is None:
        return ""
    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict):
        for key in ("text", "answer", "output", "content", "message", "value"):
            if isinstance(payload.get(key), str):
                return payload[key]
    return json.dumps(payload, ensure_ascii=False, default=str)


def _context_of(payload: Any) -> str:
    if payload is None:
        return ""
    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict):
        if isinstance(payload.get("context"), str):
            return payload["context"]
        if isinstance(payload.get("matches"), list):
            return "\n\n---\n\n".join(str(m.get("text", "")) for m in payload["matches"])
        if isinstance(payload.get("documents"), list):
            return "\n\n---\n\n".join(str(d.get("text", "")) for d in payload["documents"])
    return ""


class LLMNode(BaseNode):
    type = "llm"
    category = "ai"
    label = "LLM"
    color = "#ec4899"
    icon = "sparkles"
    description = "Appel à un modèle (OpenAI, OpenRouter, Vertex, Ollama, vLLM) avec streaming."
    inputs = [
        {"id": "prompt", "label": "Prompt"},
        {"id": "context", "label": "Contexte RAG"},
    ]
    outputs = [{"id": "output", "label": "Réponse"}]
    trigger_handles = ["prompt"]
    defaults = {
        "provider": "mock",
        "model": "flowforge-mock-1",
        "systemPrompt": DEFAULT_SYSTEM,
        "temperature": 0.7,
        "maxTokens": 512,
        "memoryEnabled": True,
        "memoryWindow": 6,
    }

    async def run(self, inputs: dict[str, list[Any]], ctx: RunContext) -> NodeOutcome:
        provider = ctx.provider_override or str(self.cfg("provider", "mock"))
        model = ctx.model_override or str(self.cfg("model", "")) or None
        client = LLMClient(provider=provider, model=model)

        prompt_payload = ctx.first(inputs, "prompt")
        context_payload = ctx.first(inputs, "context")
        question = _text_of(prompt_payload) or ctx.prompt_text()
        context = _context_of(context_payload)
        if not context and isinstance(prompt_payload, dict):
            context = _context_of(prompt_payload)
        if not question:
            raise ValueError("Le nœud LLM n'a reçu aucun prompt (connectez un Chat Input).")

        user_content = question
        if context:
            user_content = (
                f"CONTEXTE DOCUMENTAIRE:\n{context}\n\n"
                f"QUESTION UTILISATEUR:\n{question}"
            )

        messages: list[dict[str, str]] = [
            {"role": "system", "content": str(self.cfg("systemPrompt") or DEFAULT_SYSTEM)}
        ]
        memory_enabled = bool(self.cfg("memoryEnabled", True))
        if memory_enabled:
            history = await MEMORY.get(ctx.conversation_id, int(self.cfg("memoryWindow", 6)))
            messages.extend(history)
        messages.append({"role": "user", "content": user_content})

        max_tokens = int(self.cfg("maxTokens", 512))
        temperature = float(self.cfg("temperature", 0.7))
        chunks: list[str] = []
        try:
            async for token in client.stream(messages, temperature=temperature, max_tokens=max_tokens):
                chunks.append(token)
                await ctx.emit_token(self.node.id, token)
        except LLMError:
            raise
        except Exception as exc:  # réseau, timeout, etc.
            raise RuntimeError(f"Erreur LLM ({client.provider}/{client.model}): {exc}") from exc

        answer = "".join(chunks).strip()
        cost = compute_cost(client.model, client.prompt_tokens, client.completion_tokens)

        if memory_enabled:
            await MEMORY.append(ctx.conversation_id, "user", user_content)
            await MEMORY.append(ctx.conversation_id, "assistant", answer)

        return NodeOutcome(
            output={
                "text": answer,
                "provider": client.provider,
                "model": client.model,
                "conversationId": ctx.conversation_id,
                "usedContext": bool(context),
            },
            prompt_tokens=client.prompt_tokens,
            completion_tokens=client.completion_tokens,
            cost_usd=cost,
            meta={
                "provider": client.provider,
                "model": client.model,
                "temperature": temperature,
                "maxTokens": max_tokens,
                "contextChars": len(context),
                "memoryTurns": int(self.cfg("memoryWindow", 6)) if memory_enabled else 0,
            },
        )
