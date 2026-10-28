"""Workflows de démonstration créés au premier démarrage."""

from __future__ import annotations

from app.engine.nodes.code_node import DEFAULT_CODE
from app.engine.nodes.llm import DEFAULT_SYSTEM
from app.schemas import FlowEdge, FlowNode, Workflow, utcnow

RAG_ID = "wf_demo_rag"
LOGIC_ID = "wf_demo_logic"


def _n(node_id: str, node_type: str, label: str, x: float, y: float, **config) -> FlowNode:
    return FlowNode(id=node_id, type=node_type, label=label, position={"x": x, "y": y}, config=config)


def _e(source: str, target: str, source_handle: str = "output", target_handle: str = "input") -> FlowEdge:
    return FlowEdge(
        id=f"e-{source}-{target}-{source_handle}",
        source=source,
        target=target,
        sourceHandle=source_handle,
        targetHandle=target_handle,
    )


def demo_rag_workflow() -> Workflow:
    nodes = [
        _n("in", "input", "Chat Input", 0, 250, field="prompt"),
        _n("src-index", "source", "Source · Confluence", 250, 40, kind="confluence", confluenceSpaceKey="DEMO"),
        _n(
            "vs-index",
            "vectorStore",
            "Vector Store · index",
            640,
            60,
            operation="index",
            storeId="confluence-demo",
            chunkSize=700,
            chunkOverlap=100,
            reset=True,
        ),
        _n(
            "vs-query",
            "vectorStore",
            "Vector Store · query",
            500,
            300,
            operation="query",
            storeId="confluence-demo",
            topK=4,
        ),
        _n(
            "llm",
            "llm",
            "LLM",
            750,
            230,
            provider="mock",
            model="flowforge-mock-1",
            systemPrompt=DEFAULT_SYSTEM,
            temperature=0.3,
            maxTokens=600,
            memoryEnabled=True,
            memoryWindow=6,
        ),
        _n("out", "output", "Output", 1000, 230, format="text", title="Réponse RAG"),
    ]
    edges = [
        _e("src-index", "vs-index"),
        _e("vs-index", "vs-query", "output", "input"),   # déclenche le retrieval après indexation
        _e("in", "vs-query", "output", "input"),
        _e("in", "llm", "output", "prompt"),
        _e("vs-query", "llm", "output", "context"),
        _e("llm", "out"),
    ]
    now = utcnow()
    return Workflow(
        id=RAG_ID,
        name="RAG · Confluence + Vector Store",
        description="Ingestion Confluence → chunking/embeddings → retrieval → LLM avec mémoire.",
        nodes=nodes,
        edges=edges,
        createdAt=now,
        updatedAt=now,
    )


def demo_logic_workflow() -> Workflow:
    nodes = [
        _n("in", "input", "Chat Input", 0, 350, field="prompt"),
        _n("src", "source", "Source · Drive", 240, 30, kind="drive"),
        _n("vs-index", "vectorStore", "Vector Store · index", 480, 30,
           operation="index", storeId="drive-demo", reset=False),
        _n("vs-query", "vectorStore", "Vector Store · query", 720, 30,
           operation="query", storeId="drive-demo", topK=3),
        _n("tpl", "template", "Prompt Template", 240, 350,
           template="Question: {{text}}\n\nRéponds en 3 points clés, en citant les sources."),
        _n("cond", "condition", "Router · urgent ?", 480, 350,
           mode="contains", keywords="urgent, incident, panne"),
        _n("llm-a", "llm", "LLM · urgence", 960, 150, provider="mock", model="flowforge-mock-1",
           systemPrompt="Tu es un agent de crise. Réponds en 3 actions concrètes, très court.",
           temperature=0.2, maxTokens=400),
        _n("llm-b", "llm", "LLM · standard", 960, 480, provider="mock", model="flowforge-mock-1",
           systemPrompt="Tu es un assistant documentaire. Réponds de façon pédagogique.",
           temperature=0.6, maxTokens=400),
        _n("gate", "logicGate", "Porte OR", 1200, 320, gate="or"),
        _n("code", "code", "Code · normalisation", 1440, 320, code=DEFAULT_CODE, timeout=10),
        _n("out", "output", "Output", 1680, 320, format="json", title="Diagnostic"),
    ]
    edges = [
        _e("src", "vs-index"),
        _e("vs-index", "vs-query", "output", "input"),  # séquencement : indexer puis requêter
        _e("in", "vs-query", "output", "input"),
        _e("in", "tpl"),
        _e("tpl", "cond"),
        _e("cond", "llm-a", "true", "prompt"),
        _e("cond", "llm-b", "false", "prompt"),
        _e("vs-query", "llm-a", "output", "context"),
        _e("vs-query", "llm-b", "output", "context"),
        _e("llm-a", "gate", "output", "input1"),
        _e("llm-b", "gate", "output", "input2"),
        _e("gate", "code"),
        _e("code", "out"),
    ]
    now = utcnow()
    return Workflow(
        id=LOGIC_ID,
        name="Routing conditionnel · urgence",
        description="Router par mots-clés, deux agents LLM, porte OR, transformation Python.",
        nodes=nodes,
        edges=edges,
        createdAt=now,
        updatedAt=now,
    )


def all_templates() -> list[Workflow]:
    return [demo_rag_workflow(), demo_logic_workflow()]
