"""Construction et validation du DAG à partir du JSON visuel (React Flow)."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field

from app.schemas import FlowEdge, FlowNode, Workflow


class GraphError(ValueError):
    pass


@dataclass
class CompiledGraph:
    nodes: dict[str, FlowNode]
    incoming: dict[str, list[FlowEdge]] = field(default_factory=lambda: defaultdict(list))
    outgoing: dict[str, list[FlowEdge]] = field(default_factory=lambda: defaultdict(list))
    levels: list[list[str]] = field(default_factory=list)

    def node_label(self, node_id: str) -> str:
        node = self.nodes.get(node_id)
        return (node.label or node.type) if node else node_id


def compile_graph(workflow: Workflow) -> CompiledGraph:
    nodes = {n.id: n for n in workflow.nodes}
    if not nodes:
        raise GraphError("Le workflow ne contient aucun nœud.")
    if len(nodes) != len(workflow.nodes):
        raise GraphError("Identifiants de nœuds dupliqués.")

    incoming: dict[str, list[FlowEdge]] = defaultdict(list)
    outgoing: dict[str, list[FlowEdge]] = defaultdict(list)
    for edge in workflow.edges:
        if edge.source not in nodes:
            raise GraphError(f"Arête {edge.id}: source inconnue '{edge.source}'.")
        if edge.target not in nodes:
            raise GraphError(f"Arête {edge.id}: cible inconnue '{edge.target}'.")
        if edge.source == edge.target:
            raise GraphError(f"Arête {edge.id}: boucle sur soi-même.")
        incoming[edge.target].append(edge)
        outgoing[edge.source].append(edge)

    # Kahn + détection de cycle + niveaux (parallélisme)
    indegree = {nid: len(incoming[nid]) for nid in nodes}
    queue = deque([nid for nid, deg in indegree.items() if deg == 0])
    levels: list[list[str]] = []
    seen: list[str] = []
    while queue:
        level = list(queue)
        queue.clear()
        levels.append(level)
        for nid in level:
            seen.append(nid)
            for edge in outgoing[nid]:
                indegree[edge.target] -= 1
                if indegree[edge.target] == 0:
                    queue.append(edge.target)
    if len(seen) != len(nodes):
        cyclic = sorted(set(nodes) - set(seen))
        raise GraphError(
            "Cycle détecté dans le graphe (les workflow doivent être des DAG). Nœuds concernés: "
            + ", ".join(cyclic)
        )

    return CompiledGraph(nodes=nodes, incoming=incoming, outgoing=outgoing, levels=levels)


def topological_order(workflow: Workflow) -> list[str]:
    graph = compile_graph(workflow)
    return [nid for level in graph.levels for nid in level]
