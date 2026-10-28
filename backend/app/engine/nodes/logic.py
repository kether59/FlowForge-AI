from __future__ import annotations

import json
import re
from typing import Any

from app.engine.context import RunContext
from app.engine.nodes.base import BaseNode, NodeOutcome


class NodeSkipped(Exception):
    """Levée quand un bloc décide de ne pas propager l'exécution."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("text", "answer", "output", "content", "message", "value"):
            if isinstance(value.get(key), str):
                return value[key]
        return json.dumps(value, ensure_ascii=False, default=str)
    return str(value)


def _truthy(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, (list, dict)):
        return len(value) > 0
    text = str(value).strip().lower()
    return text not in {"", "false", "0", "no", "non", "none", "null", "[]", "{}"}


SAFE_EXPR = re.compile(r"^[\w\s\.\[\]\(\)\"'=!<>&|+\-*/%,:]+$", re.UNICODE)


class ConditionNode(BaseNode):
    type = "condition"
    category = "logic"
    label = "Condition / Router"
    color = "#6366f1"
    icon = "git-branch"
    description = "Aiguille le flux vers True/False selon une expression ou des mots-clés."
    inputs = [{"id": "input", "label": "Entrée"}]
    outputs = [
        {"id": "true", "label": "True"},
        {"id": "false", "label": "False"},
    ]
    defaults = {
        "mode": "expression",  # expression | contains | regex | llm? (extensible)
        "expression": "len(text) > 0",
        "keywords": "urgent, erreur",
        "pattern": r"\b(bonjour|salut)\b",
        "caseSensitive": False,
    }

    async def run(self, inputs: dict[str, list[Any]], ctx: RunContext) -> NodeOutcome:
        payload = ctx.first(inputs)
        text = _text(payload)
        mode = str(self.cfg("mode", "expression"))
        detail: dict[str, Any] = {"mode": mode, "inputPreview": text[:200]}

        if mode == "contains":
            keywords = [k.strip() for k in str(self.cfg("keywords", "")).split(",") if k.strip()]
            haystack = text if self.cfg("caseSensitive") else text.lower()
            matched = [k for k in keywords if (k if self.cfg("caseSensitive") else k.lower()) in haystack]
            decision = bool(matched)
            detail["matched"] = matched
        elif mode == "regex":
            flags = 0 if self.cfg("caseSensitive") else re.IGNORECASE
            match = re.search(str(self.cfg("pattern", "")), text, flags)
            decision = match is not None
            detail["match"] = match.group(0) if match else None
        else:
            expression = str(self.cfg("expression", "True"))
            if not SAFE_EXPR.match(expression):
                raise ValueError(f"Expression non autorisée: {expression!r}")
            scope = {
                "text": text,
                "payload": payload,
                "input": payload,
                "len": len,
                "float": float,
                "int": int,
                "str": str,
                "bool": bool,
                "lower": str.lower,
                "true": True,
                "false": False,
            }
            try:
                decision = bool(eval(expression, {"__builtins__": {}}, scope))  # noqa: S307
            except Exception as exc:
                raise ValueError(f"Expression invalide ({expression}): {exc}") from exc
            detail["expression"] = expression

        detail["decision"] = decision
        handle = "true" if decision else "false"
        return NodeOutcome(
            output={"text": text, "decision": decision, "branch": handle, "detail": detail},
            active_handles=[handle],
            meta=detail,
        )


class LogicGateNode(BaseNode):
    type = "logicGate"
    category = "logic"
    label = "Porte logique"
    color = "#7c3aed"
    icon = "gate"
    description = "Synchronise plusieurs branches : AND, OR ou XOR."
    inputs = [
        {"id": "input1", "label": "A"},
        {"id": "input2", "label": "B"},
        {"id": "input3", "label": "C"},
    ]
    outputs = [{"id": "output", "label": "Résultat"}]
    defaults = {"gate": "and"}

    async def run(self, inputs: dict[str, list[Any]], ctx: RunContext) -> NodeOutcome:
        gate = str(self.cfg("gate", "and")).lower()
        values = [(handle, ctx.first({handle: vals})) for handle, vals in inputs.items() if vals]
        truth = [(h, _truthy(v)) for h, v in values]
        states = [t for _, t in truth]

        if gate == "and":
            decision = all(states) and len(states) > 0
        elif gate == "or":
            decision = any(states)
        elif gate == "xor":
            decision = sum(1 for s in states if s) == 1
        elif gate == "nand":
            decision = not (all(states) and len(states) > 0)
        else:
            raise ValueError(f"Porte inconnue: {gate}")

        if not decision:
            raise NodeSkipped(f"Porte {gate.upper()} non satisfaite ({truth}).")

        merged = [v for _, v in values]
        return NodeOutcome(
            output={
                "text": "\n".join(_text(v) for v in merged if _text(v)),
                "values": merged,
                "gate": gate,
                "inputs": truth,
            },
            meta={"gate": gate, "inputs": len(states), "truth": truth},
        )


class MergeNode(BaseNode):
    type = "merge"
    category = "logic"
    label = "Merge"
    color = "#0891b2"
    icon = "merge"
    description = "Fusionne plusieurs branches (concaténation, tableau ou objet)."
    inputs = [
        {"id": "input1", "label": "A"},
        {"id": "input2", "label": "B"},
        {"id": "input3", "label": "C"},
    ]
    outputs = [{"id": "output", "label": "Fusion"}]
    defaults = {"mode": "concat", "separator": "\n\n"}

    async def run(self, inputs: dict[str, list[Any]], ctx: RunContext) -> NodeOutcome:
        ordered: list[tuple[str, Any]] = []
        for handle in ("input1", "input2", "input3"):
            for value in inputs.get(handle, []):
                ordered.append((handle, value))
        for handle, values in inputs.items():
            if handle not in {"input1", "input2", "input3"}:
                ordered.extend((handle, v) for v in values)
        if not ordered:
            raise ValueError("Aucune entrée à fusionner.")

        mode = str(self.cfg("mode", "concat"))
        meta: dict[str, Any] = {"mode": mode, "branches": len(ordered)}

        if mode == "array":
            output: Any = {"items": [v for _, v in ordered], "text": "\n".join(_text(v) for _, v in ordered)}
        elif mode == "object":
            output = {
                "text": "\n".join(_text(v) for _, v in ordered),
                **{handle: value for handle, value in ordered},
            }
        elif mode == "first":
            output = ordered[0][1]
        else:  # concat
            separator = str(self.cfg("separator", "\n\n"))
            text = separator.join(_text(v) for _, v in ordered if _text(v))
            output = {"text": text, "parts": len(ordered)}
            meta["chars"] = len(text)

        return NodeOutcome(output=output, meta=meta)


class PromptTemplateNode(BaseNode):
    type = "template"
    category = "logic"
    label = "Prompt Template"
    color = "#d97706"
    icon = "braces"
    description = "Construit un prompt avec des variables {{input}}, {{context}}, etc."
    inputs = [{"id": "input", "label": "Entrée"}]
    outputs = [{"id": "output", "label": "Prompt"}]
    defaults = {"template": "Question: {{text}}\n\nRéponds de façon structurée en 3 points."}

    async def run(self, inputs: dict[str, list[Any]], ctx: RunContext) -> NodeOutcome:
        payload = ctx.first(inputs)
        text = _text(payload)
        context = ""
        if isinstance(payload, dict):
            context = _text(payload.get("context")) if payload.get("context") else ""
        template = str(self.cfg("template", "{{text}}"))

        def replace(match: re.Match[str]) -> str:
            key = match.group(1).strip()
            mapping = {"input": text, "text": text, "context": context, "prompt": ctx.prompt_text()}
            if key in mapping:
                return mapping[key]
            if isinstance(payload, dict) and key in payload:
                return _text(payload[key])
            return match.group(0)

        rendered = re.sub(r"\{\{\s*([\w\.]+)\s*\}\}", replace, template)
        return NodeOutcome(
            output={"text": rendered, "template": template},
            meta={"chars": len(rendered)},
        )
