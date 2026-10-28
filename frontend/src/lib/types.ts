export type HandleSpec = { id: string; label: string }

export type NodeCategory = 'io' | 'data' | 'ai' | 'logic' | 'code'

export interface NodeTypeSpec {
  type: string
  label: string
  category: NodeCategory
  description: string
  color: string
  icon: string
  inputs: HandleSpec[]
  outputs: HandleSpec[]
  defaults: Record<string, any>
}

export interface ApiNode {
  id: string
  type: string
  label?: string | null
  position: { x: number; y: number }
  config: Record<string, any>
}

export interface ApiEdge {
  id: string
  source: string
  target: string
  sourceHandle?: string | null
  targetHandle?: string | null
}

export interface Workflow {
  id: string
  name: string
  description: string
  nodes: ApiNode[]
  edges: ApiEdge[]
  createdAt: string
  updatedAt: string
}

export interface WorkflowSummary {
  id: string
  name: string
  description: string
  nodeCount: number
  updatedAt: string
}

export type NodeStatus = 'idle' | 'queued' | 'running' | 'success' | 'error' | 'skipped'

export interface NodeUsage {
  nodeId: string
  nodeType: string
  label?: string | null
  status: NodeStatus
  startedAt?: string | null
  finishedAt?: string | null
  latencyMs?: number | null
  promptTokens: number
  completionTokens: number
  totalTokens: number
  costUsd: number
  input?: any
  output?: any
  error?: string | null
  meta: Record<string, any>
}

export interface Execution {
  id: string
  workflowId: string
  workflowName: string
  status: NodeStatus
  trigger: Record<string, any>
  startedAt: string
  finishedAt?: string | null
  durationMs?: number | null
  nodes: NodeUsage[]
  tokens: number
  costUsd: number
  finalOutput?: any
  error?: string | null
}

export interface ProviderInfo {
  label: string
  models: string[]
  requiresKey: boolean
  configured: boolean
}

export interface ProvidersResponse {
  default: string
  providers: Record<string, ProviderInfo>
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  streaming?: boolean
  meta?: { tokens?: number; costUsd?: number; latencyMs?: number; model?: string; error?: boolean }
}

export interface FlowNodeData extends Record<string, unknown> {
  label: string
  nodeType: string
  config: Record<string, any>
  spec?: NodeTypeSpec
  status: NodeStatus
  latencyMs?: number | null
  totalTokens?: number
  costUsd?: number
  error?: string | null
}

export type WsEvent =
  | { type: 'connected'; room: string }
  | { type: 'run.started'; runId: string; data: Execution }
  | { type: 'run.finished'; runId: string; data: Execution }
  | { type: 'run.failed'; runId: string; data: Execution }
  | { type: 'node.started'; runId: string; nodeId: string; data: NodeUsage }
  | { type: 'node.finished'; runId: string; nodeId: string; data: NodeUsage }
  | { type: 'node.token'; runId: string; nodeId: string; data: { token: string } }
  | { type: 'edge.active'; runId: string; data: { edgeId: string; source: string; target: string } }
  | { type: 'error'; error: string }
