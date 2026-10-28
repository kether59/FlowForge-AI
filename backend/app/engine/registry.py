from __future__ import annotations

from typing import Any

from app.engine.nodes import (
    BaseNode,
    CodeNode,
    ConditionNode,
    InputNode,
    LLMNode,
    LogicGateNode,
    MergeNode,
    OutputNode,
    PromptTemplateNode,
    SourceNode,
    VectorStoreNode,
)
from app.schemas import FlowNode

NODE_CLASSES: dict[str, type[BaseNode]] = {
    cls.type: cls
    for cls in (
        InputNode,
        OutputNode,
        SourceNode,
        VectorStoreNode,
        LLMNode,
        ConditionNode,
        LogicGateNode,
        MergeNode,
        PromptTemplateNode,
        CodeNode,
    )
}

CATEGORY_ORDER = ["io", "data", "ai", "logic", "code"]


def node_specs() -> list[dict[str, Any]]:
    specs = []
    for cls in NODE_CLASSES.values():
        specs.append(
            {
                "type": cls.type,
                "label": cls.label,
                "category": cls.category,
                "description": cls.description,
                "color": cls.color,
                "icon": cls.icon,
                "inputs": cls.inputs,
                "outputs": cls.outputs,
                "defaults": cls.defaults,
            }
        )
    return sorted(specs, key=lambda s: (CATEGORY_ORDER.index(s["category"]), s["label"]))


def build_node(node: FlowNode) -> BaseNode:
    cls = NODE_CLASSES.get(node.type)
    if not cls:
        raise ValueError(f"Type de nœud inconnu: '{node.type}'")
    return cls(node)
