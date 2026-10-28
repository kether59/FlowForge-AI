"""Tests du moteur d'exécution (sans dépendance à un provider LLM externe)."""

import asyncio
import io

import pytest

from app.engine.executor import GraphExecutor
from app.engine.graph import GraphError, compile_graph
from app.engine.nodes.sandbox_runner import run_user_code
from app.schemas import FlowEdge, FlowNode, Workflow
from app.services import documents
from app.services import embeddings
from app.services.embeddings import mock_embedding
from app.services.vectorstore import VectorStore, chunk_text
from app.templates import all_templates

# Utilitaire : pytest n'a pas besoin de pytest-asyncio ici
def run(coro):
    return asyncio.run(coro)


def make_workflow(nodes, edges) -> Workflow:
    return Workflow(id="wf_test", name="test", nodes=nodes, edges=edges)


def node(node_id, node_type, **config):
    return FlowNode(id=node_id, type=node_type, label=node_id, config=config)


def edge(source, target, source_handle="output", target_handle="input"):
    return FlowEdge(id=f"{source}-{target}-{source_handle}", source=source, target=target,
                    sourceHandle=source_handle, targetHandle=target_handle)


# --------------------------------------------------------------------- graphe
def test_dag_levels_and_parallelism():
    wf = make_workflow(
        [node("a", "input"), node("b", "template"), node("c", "template"), node("d", "merge")],
        [edge("a", "b"), edge("a", "c"), edge("b", "d", "output", "input1"), edge("c", "d", "output", "input2")],
    )
    graph = compile_graph(wf)
    assert graph.levels == [["a"], ["b", "c"], ["d"]]


def test_cycle_is_rejected():
    wf = make_workflow(
        [node("a", "input"), node("b", "output")],
        [edge("a", "b"), edge("b", "a")],
    )
    with pytest.raises(GraphError):
        compile_graph(wf)


def test_unknown_edge_endpoint_is_rejected():
    wf = make_workflow([node("a", "input")], [edge("a", "ghost")])
    with pytest.raises(GraphError):
        compile_graph(wf)


# ------------------------------------------------------------------ condition
def test_condition_routes_true_branch_and_skips_other():
    wf = make_workflow(
        [
            node("in", "input", field="prompt"),
            node("cond", "condition", mode="contains", keywords="urgent,incident"),
            node("yes", "template", template="URGENT: {{text}}"),
            node("no", "template", template="normal: {{text}}"),
            node("out", "output"),
        ],
        [
            edge("in", "cond"),
            edge("cond", "yes", "true"),
            edge("cond", "no", "false"),
            edge("yes", "out"),
            edge("no", "out"),
        ],
    )
    execution = run(GraphExecutor().run(wf, run_input={"prompt": "Incident en production"}))
    statuses = {u.nodeId: u.status.value for u in execution.nodes}
    assert execution.status.value == "success"
    assert statuses["yes"] == "success"
    assert statuses["no"] == "skipped"
    assert "URGENT" in str(execution.finalOutput)


def test_logic_gate_xor_skips_when_two_inputs():
    wf = make_workflow(
        [
            node("in", "input", field="prompt"),
            node("a", "template", template="A"),
            node("b", "template", template="B"),
            node("gate", "logicGate", gate="xor"),
            node("out", "output"),
        ],
        [
            edge("in", "a"),
            edge("in", "b"),
            edge("a", "gate", "output", "input1"),
            edge("b", "gate", "output", "input2"),
            edge("gate", "out"),
        ],
    )
    execution = run(GraphExecutor().run(wf, run_input={"prompt": "x"}))
    statuses = {u.nodeId: u.status.value for u in execution.nodes}
    assert statuses["gate"] == "skipped"
    assert statuses["out"] == "skipped"


# ----------------------------------------------------------------------- RAG
def test_chunking_respects_size_and_overlap():
    text = "Phrase courte. " * 400
    chunks = chunk_text(text, size=500, overlap=100)
    assert len(chunks) > 3
    assert all(len(c) <= 520 for c in chunks)


def test_vectorstore_search_ranks_relevant_chunk_first():
    store = VectorStore("pytest-store")
    texts = [
        "La politique de congés prévoit 25 jours ouvrés par an.",
        "Le runbook d'incident P1 impose une cellule de crise sous 15 minutes.",
        "Les embeddings sont stockés dans un index vectoriel persistant.",
    ]
    store.add(texts, [mock_embedding(t) for t in texts], [{"documentName": f"doc{i}"} for i in range(3)], reset=True)
    matches = store.search(mock_embedding("incident P1 cellule de crise"), top_k=1)
    assert "runbook" in matches[0]["text"].lower()
    store.clear()


def test_vectorstore_reindexes_document_without_duplicating_chunks():
    store = VectorStore("pytest-upsert-store")
    metadata = [{"source": "upload", "documentId": "file-1", "chunkIndex": 0}]
    store.add(["ancienne version"], [mock_embedding("ancienne version")], metadata, reset=True)
    total = store.add(["nouvelle version"], [mock_embedding("nouvelle version")], metadata)

    matches = store.search(mock_embedding("nouvelle version"), top_k=2)
    assert total == 1
    assert len(matches) == 1
    assert matches[0]["text"] == "nouvelle version"
    store.clear()


def test_upload_stream_extracts_text_and_enforces_size_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(documents, "UPLOAD_DIR", tmp_path)
    content = b"Contenu du document"

    doc = documents.save_upload_stream("notes.txt", io.BytesIO(content), max_bytes=100)
    assert doc.text == content.decode()
    assert doc.metadata["size"] == len(content)

    with pytest.raises(documents.UploadTooLargeError):
        documents.save_upload_stream("large.txt", io.BytesIO(content), max_bytes=5)
    assert len(list(tmp_path.iterdir())) == 1


def test_upload_rejects_pdf_without_extractable_text(tmp_path, monkeypatch):
    monkeypatch.setattr(documents, "UPLOAD_DIR", tmp_path)
    from pypdf import PdfWriter

    pdf_path = tmp_path / "scanned.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    with pdf_path.open("wb") as output:
        writer.write(output)

    with pdf_path.open("rb") as source, pytest.raises(ValueError, match="Aucun texte extractible"):
        documents.save_upload_stream("scanned.pdf", source, max_bytes=1024)
    assert list(tmp_path.iterdir()) == [pdf_path]


def test_embeddings_are_requested_in_bounded_batches(monkeypatch):
    batches = []

    async def fake_embed_texts(texts):
        batches.append(len(texts))
        return [[float(len(texts))] for _ in texts]

    monkeypatch.setattr(embeddings, "embed_texts", fake_embed_texts)
    vectors = run(embeddings.embed_texts_batched([str(i) for i in range(205)], batch_size=100))

    assert batches == [100, 100, 5]
    assert len(vectors) == 205


def test_demo_rag_workflow_runs_end_to_end():
    wf = [w for w in all_templates() if "rag" in w.id][0]
    execution = run(GraphExecutor().run(wf, run_input={"prompt": "Comment traiter un incident ?"}))
    assert execution.status.value == "success"
    assert execution.tokens > 0
    assert all(u.status.value in ("success", "skipped") for u in execution.nodes)
    assert execution.finalOutput


def test_demo_logic_workflow_selects_a_single_llm_branch():
    wf = [w for w in all_templates() if "logic" in w.id][0]
    execution = run(GraphExecutor().run(wf, run_input={"prompt": "Incident critique sur l'API"}))
    statuses = {u.nodeId: u.status.value for u in execution.nodes}
    assert statuses["llm-a"] == "success"
    assert statuses["llm-b"] == "skipped"


# ---------------------------------------------------------------------- code
def test_code_node_returns_result_and_handles_errors():
    result, error = run(run_user_code("result = {'n': len(payload)}", [1, 2, 3], {}))
    assert error is None and result["n"] == 3

    _, error = run(run_user_code("raise ValueError('boom')", None, {}))
    assert error and "boom" in error


def test_code_node_timeout_is_enforced():
    _, error = run(run_user_code("import time\ntime.sleep(5)", None, {}, timeout=1))
    assert error and "Timeout" in error
