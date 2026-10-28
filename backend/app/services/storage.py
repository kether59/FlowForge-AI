"""Persistance légère sur fichiers JSON (workflows + exécutions).

Remplaçable par PostgreSQL/SQLite sans toucher au moteur : seules les fonctions
de ce module sont utilisées par l'API.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from app.config import DATA_DIR
from app.schemas import Execution, Workflow, WorkflowSummary, utcnow

WORKFLOW_DIR = DATA_DIR / "workflows"
RUN_DIR = DATA_DIR / "runs"
WORKFLOW_DIR.mkdir(parents=True, exist_ok=True)
RUN_DIR.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------------------- workflows
def save_workflow(wf: Workflow) -> Workflow:
    wf.updatedAt = utcnow()
    (WORKFLOW_DIR / f"{wf.id}.json").write_text(wf.model_dump_json(indent=2))
    return wf


def get_workflow(wf_id: str) -> Workflow | None:
    path = WORKFLOW_DIR / f"{wf_id}.json"
    if not path.exists():
        return None
    return Workflow.model_validate_json(path.read_text())


def list_workflows() -> list[WorkflowSummary]:
    items: list[WorkflowSummary] = []
    for path in WORKFLOW_DIR.glob("*.json"):
        try:
            wf = Workflow.model_validate_json(path.read_text())
        except Exception:
            continue
        items.append(
            WorkflowSummary(
                id=wf.id,
                name=wf.name,
                description=wf.description,
                nodeCount=len(wf.nodes),
                updatedAt=wf.updatedAt,
            )
        )
    return sorted(items, key=lambda w: w.updatedAt, reverse=True)


def delete_workflow(wf_id: str) -> bool:
    path = WORKFLOW_DIR / f"{wf_id}.json"
    if path.exists():
        path.unlink()
        return True
    return False


def new_workflow_id() -> str:
    return "wf_" + uuid.uuid4().hex[:10]


# -------------------------------------------------------------- executions
def save_execution(execution: Execution) -> None:
    (RUN_DIR / f"{execution.id}.json").write_text(execution.model_dump_json(indent=2))


def get_execution(run_id: str) -> Execution | None:
    path = RUN_DIR / f"{run_id}.json"
    if not path.exists():
        return None
    return Execution.model_validate_json(path.read_text())


def list_executions(workflow_id: str | None = None, limit: int = 30) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in RUN_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError:
            continue
        if workflow_id and data.get("workflowId") != workflow_id:
            continue
        items.append(
            {
                "id": data["id"],
                "workflowId": data.get("workflowId"),
                "workflowName": data.get("workflowName"),
                "status": data.get("status"),
                "startedAt": data.get("startedAt"),
                "finishedAt": data.get("finishedAt"),
                "durationMs": data.get("durationMs"),
                "tokens": data.get("tokens", 0),
                "costUsd": data.get("costUsd", 0.0),
                "error": data.get("error"),
            }
        )
    items.sort(key=lambda d: d.get("startedAt") or "", reverse=True)
    return items[:limit]
