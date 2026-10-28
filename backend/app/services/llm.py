"""Couche d'abstraction unifiée pour les providers LLM.

Tous les providers exposent la même interface :
    - async stream(messages, ...) -> AsyncIterator[str]   (tokens)
    - async complete(messages, ...) -> str
    - metadata (contexte, coût)

Providers supportés : OpenAI, OpenRouter, Vertex AI (Gemini), Ollama, vLLM,
et un provider "mock" déterministe qui permet de faire tourner le prototype
sans aucune clé API (streaming simulé, utile pour la démo/les tests).
"""

from __future__ import annotations

import asyncio
import json
import random
import re
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

import httpx

from app.config import get_settings

# Prix indicatifs ($ / 1K tokens) — à ajuster selon vos contrats.
PRICING: dict[str, tuple[float, float]] = {
    "gpt-4o": (0.0025, 0.010),
    "gpt-4o-mini": (0.00015, 0.0006),
    "gpt-4.1": (0.002, 0.008),
    "gpt-4.1-mini": (0.0004, 0.0016),
    "o3-mini": (0.0011, 0.0044),
    "text-embedding-3-small": (0.00002, 0.0),
    "claude-3-5-sonnet": (0.003, 0.015),
    "claude-sonnet-4": (0.003, 0.015),
    "gemini-1.5-pro": (0.00125, 0.005),
    "gemini-2.0-flash": (0.0001, 0.0004),
    "gemini-2.5-flash": (0.0003, 0.0025),
    "mistralai/mixtral-8x7b-instruct": (0.0006, 0.0006),
    "meta-llama/llama-3.1-70b-instruct": (0.0009, 0.0009),
    "qwen/qwen-2.5-72b-instruct": (0.00035, 0.0004),
    "llama3.1": (0.0, 0.0),
}


@dataclass
class LLMResult:
    text: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    model: str = ""
    provider: str = ""
    meta: dict[str, Any] = field(default_factory=dict)


def estimate_tokens(text: str) -> int:
    """Estimation grossière (~4 caractères / token) quand le provider ne renvoie pas l'usage."""
    return max(1, len(text) // 4)


def compute_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    key = model.split(":")[0]
    for name, (pin, pout) in PRICING.items():
        if key == name or key.startswith(name):
            return round(prompt_tokens / 1000 * pin + completion_tokens / 1000 * pout, 6)
    return 0.0


PROVIDERS: dict[str, dict[str, Any]] = {
    "mock": {
        "label": "Mock (hors ligne)",
        "models": ["flowforge-mock-1"],
        "requiresKey": False,
        "baseUrl": None,
    },
    "openai": {
        "label": "OpenAI",
        "models": ["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini", "gpt-4.1", "o3-mini"],
        "requiresKey": True,
        "baseUrl": "https://api.openai.com/v1",
    },
    "openrouter": {
        "label": "OpenRouter",
        "models": [
            "openai/gpt-4o-mini",
            "anthropic/claude-3.5-sonnet",
            "google/gemini-2.0-flash-001",
            "meta-llama/llama-3.1-70b-instruct",
            "qwen/qwen-2.5-72b-instruct",
        ],
        "requiresKey": True,
        "baseUrl": "https://openrouter.ai/api/v1",
    },
    "vertex": {
        "label": "Vertex AI (Gemini)",
        "models": ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-2.5-flash"],
        "requiresKey": True,
        "baseUrl": "https://generativelanguage.googleapis.com/v1beta",
    },
    "ollama": {
        "label": "Ollama (local)",
        "models": ["llama3.1", "mistral", "qwen2.5", "phi3"],
        "requiresKey": False,
        "baseUrl": "http://localhost:11434",
    },
    "vllm": {
        "label": "vLLM (local)",
        "models": ["mistralai/Mistral-7B-Instruct-v0.3", "Qwen/Qwen2.5-7B-Instruct"],
        "requiresKey": False,
        "baseUrl": "http://localhost:8000/v1",
    },
}


class LLMError(RuntimeError):
    pass


class LLMClient:
    def __init__(self, provider: str | None = None, model: str | None = None) -> None:
        self.settings = get_settings()
        self.provider = (provider or self.settings.default_provider).lower()
        if self.provider not in PROVIDERS:
            raise LLMError(f"Provider inconnu: {self.provider}")
        meta = PROVIDERS[self.provider]
        self.model = model or meta["models"][0]
        self.prompt_tokens = 0
        self.completion_tokens = 0

    # ------------------------------------------------------------------ utils
    def _api_key(self) -> str | None:
        s = self.settings
        return {
            "openai": s.openai_api_key,
            "openrouter": s.openrouter_api_key,
            "vertex": s.vertex_api_key,
        }.get(self.provider)

    @property
    def available(self) -> bool:
        if not PROVIDERS[self.provider]["requiresKey"]:
            return True
        return bool(self._api_key())

    def _base_url(self) -> str:
        s = self.settings
        override = {
            "openai": s.openai_base_url,
            "openrouter": s.openrouter_base_url,
            "ollama": s.ollama_base_url,
            "vllm": s.vllm_base_url,
            "vertex": PROVIDERS["vertex"]["baseUrl"],
        }.get(self.provider)
        return (override or PROVIDERS[self.provider]["baseUrl"] or "").rstrip("/")

    async def _post_stream(self, url: str, headers: dict, payload: dict) -> AsyncIterator[str]:
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as resp:
                if resp.status_code >= 400:
                    body = (await resp.aread()).decode(errors="ignore")
                    raise LLMError(f"{self.provider} HTTP {resp.status_code}: {body[:500]}")
                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    delta = (
                        chunk.get("choices", [{}])[0]
                        .get("delta", {})
                        .get("content")
                    )
                    if delta:
                        yield delta
                    usage = chunk.get("usage")
                    if usage:
                        self.prompt_tokens = usage.get("prompt_tokens", 0)
                        self.completion_tokens = usage.get("completion_tokens", 0)

    # --------------------------------------------------------------- mock impl
    async def _stream_mock(self, messages: list[dict], max_tokens: int) -> AsyncIterator[str]:
        user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        system = next((m["content"] for m in messages if m["role"] == "system"), "")
        context_marker = "CONTEXTE DOCUMENTAIRE"
        has_context = context_marker in user
        question = user.split("QUESTION UTILISATEUR:")[-1].strip() if "QUESTION UTILISATEUR:" in user else user
        question = re.sub(r"\s+", " ", question)[:280]

        if has_context:
            answer = (
                f"[MODE DÉMO — aucun provider LLM configuré]\n\n"
                f"Voici une synthèse basée sur les extraits récupérés par le nœud Vector Store "
                f"pour la question « {question} » :\n\n"
                f"1. Les passages indexés les plus proches traitent bien de ce sujet ; le récupérateur "
                f"a remonté les chunks par similarité cosinus sur les embeddings.\n"
                f"2. Les informations ci-dessus proviennent des documents injectés dans le contexte, "
                f"ce qui illustre la chaîne RAG complète (Source → Chunking → Embeddings → Retrieval).\n"
                f"3. Pour obtenir une vraie génération, renseignez OPENAI_API_KEY (ou un endpoint Ollama/vLLM) "
                f"dans le fichier .env, puis choisissez le provider correspondant dans le nœud LLM.\n\n"
                f"Réponse simulée, system prompt appliqué : « {system[:90] or '(aucun)'} »."
            )
        else:
            answer = (
                f"[MODE DÉMO] Réponse simulée à : « {question} ».\n\n"
                f"Ce texte est streamé token par token par le moteur d'exécution afin de valider "
                f"la boucle complète WebSocket → nœud LLM → UI. Configurez une clé API "
                f"(OpenAI, OpenRouter, Vertex) ou un serveur Ollama/vLLM pour brancher un vrai modèle."
            )
        for tok in re.findall(r"\s*\S+", answer):
            if self.completion_tokens >= max_tokens:
                break
            await asyncio.sleep(random.uniform(0.008, 0.03))
            yield tok
            self.completion_tokens += 1

    # ------------------------------------------------------------- public API
    async def stream(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 512,
    ) -> AsyncIterator[str]:
        """Yield les tokens au fur et à mesure."""
        prompt_text = "\n".join(m["content"] for m in messages)
        self.prompt_tokens = estimate_tokens(prompt_text)
        self.completion_tokens = 0

        if self.provider == "mock":
            async for tok in self._stream_mock(messages, max_tokens):
                yield tok
            return

        if not self.available:
            raise LLMError(
                f"Clé API manquante pour {self.provider}. Configurez-la dans .env "
                f"ou utilisez le provider 'mock'."
            )

        if self.provider in {"openai", "openrouter", "ollama", "vllm"}:
            headers = {"Content-Type": "application/json"}
            key = self._api_key()
            if key:
                headers["Authorization"] = f"Bearer {key}"
            if self.provider == "openrouter":
                headers["HTTP-Referer"] = "http://localhost:5173"
                headers["X-Title"] = "FlowForge AI"
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": True,
            }
            if self.provider != "openai":
                payload["stream_options"] = {"include_usage": True}
            async for tok in self._post_stream(self._base_url() + "/chat/completions", headers, payload):
                yield tok
                self.completion_tokens += 1
            return

        if self.provider == "vertex":
            key = self._api_key()
            url = (
                f"{self._base_url()}/models/{self.model}:streamGenerateContent"
                f"?alt=sse&key={key}"
            )
            system = "\n".join(m["content"] for m in messages if m["role"] == "system")
            contents = [
                {"role": "user" if m["role"] == "user" else "model", "parts": [{"text": m["content"]}]}
                for m in messages
                if m["role"] != "system"
            ]
            payload: dict[str, Any] = {
                "contents": contents,
                "generationConfig": {
                    "temperature": temperature,
                    "maxOutputTokens": max_tokens,
                },
            }
            if system:
                payload["systemInstruction"] = {"parts": [{"text": system}]}
            async with httpx.AsyncClient(timeout=120) as client:
                async with client.stream("POST", url, json=payload) as resp:
                    if resp.status_code >= 400:
                        body = (await resp.aread()).decode(errors="ignore")
                        raise LLMError(f"vertex HTTP {resp.status_code}: {body[:500]}")
                    async for line in resp.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        try:
                            chunk = json.loads(line[5:].strip())
                        except json.JSONDecodeError:
                            continue
                        for cand in chunk.get("candidates", []):
                            for part in cand.get("content", {}).get("parts", []):
                                if part.get("text"):
                                    yield part["text"]
                                    self.completion_tokens += 1
                        usage = chunk.get("usageMetadata")
                        if usage:
                            self.prompt_tokens = usage.get("promptTokenCount", self.prompt_tokens)
                            self.completion_tokens = usage.get("candidatesTokenCount", self.completion_tokens)
            return

        raise LLMError(f"Provider non implémenté: {self.provider}")

    async def complete(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 512,
    ) -> LLMResult:
        chunks: list[str] = []
        async for tok in self.stream(messages, temperature=temperature, max_tokens=max_tokens):
            chunks.append(tok)
        text = "".join(chunks)
        return LLMResult(
            text=text,
            prompt_tokens=self.prompt_tokens,
            completion_tokens=self.completion_tokens,
            cost_usd=compute_cost(self.model, self.prompt_tokens, self.completion_tokens),
            model=self.model,
            provider=self.provider,
        )
