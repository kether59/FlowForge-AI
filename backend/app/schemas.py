from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class NodeStatus(str, Enum):
    idle = "idle"
    queued = "queued"
    running = "running"
    success = "success"
    error = "error"
    skipped = "skipped"


class FlowNode(BaseModel):
    id: str
    type: str
    label: str | None = None
    position: dict[str, float] = Field(default_factory=lambda: {"x": 0, "y": 0})
    config: dict[str, Any] = Field(default_factory=dict)


class FlowEdge(BaseModel):
    id: str
    source: str
    target: str
    sourceHandle: str | None = "output"
    targetHandle: str | None = "input"


class Workflow(BaseModel):
    id: str
    name: str = "Nouveau workflow"
    description: str = ""
    nodes: list[FlowNode] = Field(default_factory=list)
    edges: list[FlowEdge] = Field(default_factory=list)
    createdAt: str = Field(default_factory=utcnow)
    updatedAt: str = Field(default_factory=utcnow)


class WorkflowSummary(BaseModel):
    id: str
    name: str
    description: str = ""
    nodeCount: int
    updatedAt: str


class NodeUsage(BaseModel):
    nodeId: str
    nodeType: str
    label: str | None = None
    status: NodeStatus = NodeStatus.idle
    startedAt: str | None = None
    finishedAt: str | None = None
    latencyMs: float | None = None
    promptTokens: int = 0
    completionTokens: int = 0
    totalTokens: int = 0
    costUsd: float = 0.0
    input: Any = None
    output: Any = None
    error: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)


class Execution(BaseModel):
    id: str
    workflowId: str
    workflowName: str = ""
    status: NodeStatus = NodeStatus.queued
    trigger: dict[str, Any] = Field(default_factory=dict)
    startedAt: str = Field(default_factory=utcnow)
    finishedAt: str | None = None
    durationMs: float | None = None
    nodes: list[NodeUsage] = Field(default_factory=list)
    tokens: int = 0
    costUsd: float = 0.0
    finalOutput: Any = None
    error: str | None = None


class RunRequest(BaseModel):
    input: dict[str, Any] = Field(default_factory=dict)
    conversationId: str | None = None
    provider: str | None = None
    model: str | None = None


class TestLLMRequest(BaseModel):
    provider: str
    model: str
    prompt: str = "Réponds simplement: bonjour"


class ConfluenceImportRequest(BaseModel):
    baseUrl: str | None = None
    email: str | None = None
    apiToken: str | None = None
    pageId: str | None = None
    spaceKey: str | None = None
    cql: str | None = None
    limit: int = 10


class DriveImportRequest(BaseModel):
    folderId: str | None = None
    fileIds: list[str] = Field(default_factory=list)
    credentialsPath: str | None = None
    limit: int = 10


class SourceDocument(BaseModel):
    id: str
    name: str
    text: str
    source: Literal["upload", "drive", "confluence", "inline"] = "inline"
    url: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class NodeTypeSpec(BaseModel):
    type: str
    label: str
    category: str
    description: str
    color: str
    icon: str
    inputs: list[dict[str, str]] = Field(default_factory=list)
    outputs: list[dict[str, str]] = Field(default_factory=list)
    defaults: dict[str, Any] = Field(default_factory=dict)
