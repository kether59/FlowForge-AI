from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar

from app.schemas import FlowNode
from app.engine.context import RunContext


@dataclass
class NodeOutcome:
    output: Any
    active_handles: list[str] | None = None  # None => toutes les sorties actives
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    meta: dict[str, Any] = field(default_factory=dict)


class BaseNode:
    """Contrat commun à tous les blocs exécutables."""

    type: ClassVar[str] = "base"
    category: ClassVar[str] = "misc"
    label: ClassVar[str] = "Bloc"
    color: ClassVar[str] = "#64748b"
    icon: ClassVar[str] = "box"
    description: ClassVar[str] = ""
    inputs: ClassVar[list[dict[str, str]]] = [{"id": "input", "label": "Entrée"}]
    outputs: ClassVar[list[dict[str, str]]] = [{"id": "output", "label": "Sortie"}]
    defaults: ClassVar[dict[str, Any]] = {}
    # Handles dont la réception déclenche l'exécution du bloc. None = tous les handles.
    # Exemple : le nœud LLM n'est déclenché que par "prompt" ; "context" est un apport
    # optionnel qui ne doit pas lancer le bloc seul.
    trigger_handles: ClassVar[list[str] | None] = None

    def __init__(self, node: FlowNode) -> None:
        self.node = node
        self.config: dict[str, Any] = {**self.defaults, **node.config}

    async def run(self, inputs: dict[str, list[Any]], ctx: RunContext) -> NodeOutcome:
        raise NotImplementedError

    # helpers -----------------------------------------------------------
    def cfg(self, key: str, default: Any = None) -> Any:
        value = self.config.get(key, default)
        return default if value is None else value
