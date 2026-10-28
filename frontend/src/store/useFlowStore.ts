import {
  addEdge,
  applyEdgeChanges,
  applyNodeChanges,
  type Connection,
  type Edge,
  type EdgeChange,
  type Node,
  type NodeChange,
} from '@xyflow/react'
import { create } from 'zustand'

import { api } from '../lib/api'
import type {
  ChatMessage,
  Execution,
  FlowNodeData,
  NodeStatus,
  NodeTypeSpec,
  ProvidersResponse,
  WsEvent,
  Workflow,
  WorkflowSummary,
} from '../lib/types'

const uid = () => Math.random().toString(36).slice(2, 10)

const toFlowNodes = (wf: Workflow, specs: Record<string, NodeTypeSpec>): Node<FlowNodeData>[] =>
  wf.nodes.map((n) => ({
    id: n.id,
    type: 'flowforge',
    position: n.position,
    data: {
      label: n.label || specs[n.type]?.label || n.type,
      nodeType: n.type,
      config: { ...(specs[n.type]?.defaults ?? {}), ...n.config },
      spec: specs[n.type],
      status: 'idle' as NodeStatus,
      latencyMs: null,
      totalTokens: 0,
      costUsd: 0,
      error: null,
    },
  }))

const toFlowEdges = (wf: Workflow): Edge[] =>
  wf.edges.map((e) => ({
    id: e.id,
    source: e.source,
    target: e.target,
    sourceHandle: e.sourceHandle ?? 'output',
    targetHandle: e.targetHandle ?? 'input',
    type: 'smoothstep',
    animated: false,
    style: { stroke: '#3d4a67', strokeWidth: 2 },
    label: undefined,
  }))

interface FlowState {
  specs: NodeTypeSpec[]
  specByType: Record<string, NodeTypeSpec>
  providers: ProvidersResponse | null
  workflows: WorkflowSummary[]
  workflow: Workflow | null
  nodes: Node<FlowNodeData>[]
  edges: Edge[]
  selectedNodeId: string | null
  dirty: boolean
  loading: boolean
  saving: boolean
  error: string | null
  toast: string | null

  execution: Execution | null
  running: boolean
  streaming: Record<string, string>
  activeEdges: string[]

  chat: ChatMessage[]
  conversationId: string
  streamingNodeId: string | null
  wsStatus: 'connecting' | 'open' | 'closed'
  providerOverride: string | null
  modelOverride: string | null

  bootstrap: () => Promise<void>
  openWorkflow: (id: string) => Promise<void>
  createWorkflow: () => Promise<void>
  duplicateWorkflow: () => Promise<void>
  deleteWorkflow: () => Promise<void>
  renameWorkflow: (name: string) => void
  setDescription: (description: string) => void
  save: () => Promise<void>
  validate: () => Promise<void>

  onNodesChange: (changes: NodeChange[]) => void
  onEdgesChange: (changes: EdgeChange[]) => void
  onConnect: (connection: Connection) => void
  addNode: (type: string, position: { x: number; y: number }) => void
  selectNode: (id: string | null) => void
  updateConfig: (id: string, patch: Record<string, any>) => void
  updateLabel: (id: string, label: string) => void
  deleteNode: (id: string) => void

  run: (prompt: string) => Promise<void>
  applyEvent: (event: WsEvent) => void
  setWsStatus: (status: 'connecting' | 'open' | 'closed') => void
  setProviderOverride: (provider: string | null, model?: string | null) => void
  clearChat: () => Promise<void>
  setToast: (message: string | null) => void
}

export const useFlowStore = create<FlowState>((set, get) => ({
  specs: [],
  specByType: {},
  providers: null,
  workflows: [],
  workflow: null,
  nodes: [],
  edges: [],
  selectedNodeId: null,
  dirty: false,
  loading: true,
  saving: false,
  error: null,
  toast: null,

  execution: null,
  running: false,
  streaming: {},
  activeEdges: [],

  chat: [],
  conversationId: `conv_${uid()}`,
  streamingNodeId: null,
  wsStatus: 'closed',
  providerOverride: null,
  modelOverride: null,

  bootstrap: async () => {
    set({ loading: true, error: null })
    try {
      const [specs, providers, workflows] = await Promise.all([
        api.nodeTypes(),
        api.providers(),
        api.listWorkflows(),
      ])
      const specByType = Object.fromEntries(specs.map((s) => [s.type, s]))
      set({ specs, specByType, providers, workflows })
      if (workflows.length > 0) {
        await get().openWorkflow(workflows[0].id)
      } else {
        set({ loading: false })
      }
    } catch (err: any) {
      set({ loading: false, error: err?.message ?? 'API indisponible' })
    }
  },

  openWorkflow: async (id) => {
    try {
      const wf = await api.getWorkflow(id)
      const { specByType } = get()
      set({
        workflow: wf,
        nodes: toFlowNodes(wf, specByType),
        edges: toFlowEdges(wf),
        selectedNodeId: null,
        dirty: false,
        loading: false,
        execution: null,
        streaming: {},
        activeEdges: [],
        conversationId: `conv_${wf.id}`,
        chat: [],
      })
    } catch (err: any) {
      set({ error: err?.message ?? 'Workflow introuvable', loading: false })
    }
  },

  createWorkflow: async () => {
    const wf = await api.createWorkflow('Nouveau workflow')
    set((s) => ({ workflows: [{ id: wf.id, name: wf.name, description: '', nodeCount: 0, updatedAt: wf.updatedAt }, ...s.workflows] }))
    await get().openWorkflow(wf.id)
  },

  duplicateWorkflow: async () => {
    const wf = get().workflow
    if (!wf) return
    const clone = await api.duplicateWorkflow(wf.id)
    const list = await api.listWorkflows()
    set({ workflows: list })
    await get().openWorkflow(clone.id)
    set({ toast: 'Workflow dupliqué' })
  },

  deleteWorkflow: async () => {
    const wf = get().workflow
    if (!wf) return
    await api.deleteWorkflow(wf.id)
    const list = await api.listWorkflows()
    set({ workflows: list })
    if (list.length > 0) await get().openWorkflow(list[0].id)
    else set({ workflow: null, nodes: [], edges: [] })
  },

  renameWorkflow: (name) =>
    set((s) => (s.workflow ? { workflow: { ...s.workflow, name }, dirty: true } : {})),

  setDescription: (description) =>
    set((s) => (s.workflow ? { workflow: { ...s.workflow, description }, dirty: true } : {})),

  save: async () => {
    const { workflow, nodes, edges } = get()
    if (!workflow) return
    set({ saving: true, error: null })
    try {
      const payload: Workflow = {
        ...workflow,
        nodes: nodes.map((n) => ({
          id: n.id,
          type: n.data.nodeType,
          label: n.data.label,
          position: n.position,
          config: n.data.config,
        })),
        edges: edges.map((e) => ({
          id: e.id,
          source: e.source,
          target: e.target,
          sourceHandle: e.sourceHandle ?? null,
          targetHandle: e.targetHandle ?? null,
        })),
      }
      const saved = await api.saveWorkflow(payload)
      const workflows = await api.listWorkflows()
      set({ workflow: saved, dirty: false, workflows, toast: 'Workflow enregistré' })
    } catch (err: any) {
      set({ error: err?.message ?? "Échec de l'enregistrement" })
    } finally {
      set({ saving: false })
    }
  },

  validate: async () => {
    const { workflow, nodes, edges } = get()
    if (!workflow) return
    const payload: Workflow = {
      ...workflow,
      nodes: nodes.map((n) => ({
        id: n.id,
        type: n.data.nodeType,
        label: n.data.label,
        position: n.position,
        config: n.data.config,
      })),
      edges: edges.map((e) => ({
        id: e.id,
        source: e.source,
        target: e.target,
        sourceHandle: e.sourceHandle ?? null,
        targetHandle: e.targetHandle ?? null,
      })),
    }
    const res = await api.validate(payload)
    set({ toast: res.valid ? '✅ Graphe valide (DAG)' : `❌ ${res.error}` })
  },

  onNodesChange: (changes) => {
    set((s) => ({ nodes: applyNodeChanges(changes, s.nodes) as Node<FlowNodeData>[] }))
    if (changes.some((c) => c.type === 'position' || c.type === 'add' || c.type === 'remove')) {
      set({ dirty: true })
    }
  },

  onEdgesChange: (changes) => {
    set((s) => ({ edges: applyEdgeChanges(changes, s.edges) as Edge[] }))
    if (changes.some((c) => c.type === 'add' || c.type === 'remove')) set({ dirty: true })
  },

  onConnect: (connection) => {
    const { specByType, nodes } = get()
    const target = nodes.find((n) => n.id === connection.target)
    const spec = target ? specByType[target.data.nodeType] : undefined
    const sourceHandle = connection.sourceHandle ?? 'output'
    const targetHandle = connection.targetHandle ?? spec?.inputs[0]?.id ?? 'input'
    set((s) => ({
      edges: addEdge(
        {
          ...connection,
          sourceHandle,
          targetHandle,
          id: `e_${uid()}`,
          type: 'smoothstep',
          style: { stroke: '#3d4a67', strokeWidth: 2 },
        },
        s.edges,
      ),
      dirty: true,
    }))
  },

  addNode: (type, position) => {
    const spec = get().specByType[type]
    if (!spec) return
    const id = `${type}_${uid()}`
    const node: Node<FlowNodeData> = {
      id,
      type: 'flowforge',
      position,
      data: {
        label: spec.label,
        nodeType: type,
        config: { ...spec.defaults },
        spec,
        status: 'idle',
        latencyMs: null,
        totalTokens: 0,
        costUsd: 0,
        error: null,
      },
    }
    set((s) => ({ nodes: [...s.nodes, node], selectedNodeId: id, dirty: true }))
  },

  selectNode: (id) => set({ selectedNodeId: id }),

  updateConfig: (id, patch) =>
    set((s) => ({
      nodes: s.nodes.map((n) =>
        n.id === id ? { ...n, data: { ...n.data, config: { ...n.data.config, ...patch } } } : n,
      ),
      dirty: true,
    })),

  updateLabel: (id, label) =>
    set((s) => ({
      nodes: s.nodes.map((n) => (n.id === id ? { ...n, data: { ...n.data, label } } : n)),
      dirty: true,
    })),

  deleteNode: (id) =>
    set((s) => ({
      nodes: s.nodes.filter((n) => n.id !== id),
      edges: s.edges.filter((e) => e.source !== id && e.target !== id),
      selectedNodeId: s.selectedNodeId === id ? null : s.selectedNodeId,
      dirty: true,
    })),

  run: async (prompt) => {
    const { workflow, running, conversationId, providerOverride, modelOverride } = get()
    if (!workflow || running) return
    if (get().dirty) await get().save()

    const userMessage: ChatMessage = { id: uid(), role: 'user', content: prompt }
    const assistantId = uid()
    const assistantMessage: ChatMessage = {
      id: assistantId,
      role: 'assistant',
      content: '',
      streaming: true,
      meta: {},
    }
    set((s) => ({
      chat: [...s.chat, userMessage, assistantMessage],
      running: true,
      execution: null,
      streaming: {},
      activeEdges: [],
      streamingNodeId: null,
      edges: s.edges.map((e) => ({
        ...e,
        animated: false,
        style: { stroke: '#3d4a67', strokeWidth: 2 },
      })),
      nodes: s.nodes.map((n) => ({
        ...n,
        data: {
          ...n.data,
          status: 'idle' as NodeStatus,
          latencyMs: null,
          totalTokens: 0,
          costUsd: 0,
          error: null,
        },
      })),
    }))

    try {
      const execution = await api.run(workflow.id, {
        input: { prompt },
        conversationId,
        ...(providerOverride ? { provider: providerOverride } : {}),
        ...(modelOverride ? { model: modelOverride } : {}),
      })
      const text =
        typeof execution.finalOutput === 'string'
          ? execution.finalOutput
          : execution.finalOutput?.text ?? '(aucune sortie)'
      const llmNode = [...execution.nodes].reverse().find((n) => n.nodeType === 'llm')
      set((s) => ({
        execution,
        running: false,
        streamingNodeId: null,
        nodes: s.nodes.map((n) => {
          const usage = execution.nodes.find((u) => u.nodeId === n.id)
          return usage
            ? {
                ...n,
                data: {
                  ...n.data,
                  status: usage.status,
                  latencyMs: usage.latencyMs,
                  totalTokens: usage.totalTokens,
                  costUsd: usage.costUsd,
                  error: usage.error,
                },
              }
            : n
        }),
        chat: s.chat.map((m) =>
          m.id === assistantId
            ? {
                ...m,
                content: execution.status === 'error' ? m.content || `❌ ${execution.error}` : text,
                streaming: false,
                meta: {
                  tokens: execution.tokens,
                  costUsd: execution.costUsd,
                  latencyMs: execution.durationMs ?? undefined,
                  model: llmNode?.meta?.model as string | undefined,
                  error: execution.status === 'error',
                },
              }
            : m,
        ),
      }))
    } catch (err: any) {
      set((s) => ({
        running: false,
        streamingNodeId: null,
        error: err?.message ?? 'Erreur d’exécution',
        chat: s.chat.map((m) =>
          m.id === assistantId
            ? { ...m, content: `❌ ${err?.message ?? 'Erreur'}`, streaming: false, meta: { error: true } }
            : m,
        ),
      }))
    }
  },

  applyEvent: (event) => {
    switch (event.type) {
      case 'run.started': {
        set((s) => ({
          execution: event.data,
          running: true,
          streaming: {},
          activeEdges: [],
          edges: s.edges.map((e) => ({
            ...e,
            animated: false,
            style: { stroke: '#3d4a67', strokeWidth: 2 },
          })),
        }))
        break
      }
      case 'node.started': {
        const usage = event.data
        set((s) => ({
          nodes: s.nodes.map((n) =>
            n.id === usage.nodeId ? { ...n, data: { ...n.data, status: 'running', error: null } } : n,
          ),
          streamingNodeId: usage.nodeType === 'llm' ? usage.nodeId : s.streamingNodeId,
        }))
        break
      }
      case 'node.token': {
        const { nodeId } = event
        set((s) => ({
          streaming: { ...s.streaming, [nodeId]: (s.streaming[nodeId] ?? '') + event.data.token },
          chat: s.chat.map((m, idx) =>
            m.streaming && idx === s.chat.length - 1
              ? { ...m, content: m.content + event.data.token }
              : m,
          ),
        }))
        break
      }
      case 'node.finished': {
        const usage = event.data
        set((s) => ({
          nodes: s.nodes.map((n) =>
            n.id === usage.nodeId
              ? {
                  ...n,
                  data: {
                    ...n.data,
                    status: usage.status,
                    latencyMs: usage.latencyMs,
                    totalTokens: usage.totalTokens,
                    costUsd: usage.costUsd,
                    error: usage.error,
                  },
                }
              : n,
          ),
          execution: s.execution
            ? {
                ...s.execution,
                nodes: s.execution.nodes.map((u) => (u.nodeId === usage.nodeId ? usage : u)),
              }
            : s.execution,
        }))
        break
      }
      case 'edge.active': {
        set((s) => ({
          activeEdges: [...new Set([...s.activeEdges, event.data.edgeId])],
          edges: s.edges.map((e) =>
            e.id === event.data.edgeId
              ? { ...e, animated: true, style: { stroke: '#818cf8', strokeWidth: 2.5 } }
              : e,
          ),
        }))
        break
      }
      case 'run.finished':
      case 'run.failed': {
        set((s) => ({
          execution: event.data,
          running: false,
          streamingNodeId: null,
          chat: s.chat.map((m, idx) =>
            idx === s.chat.length - 1 && m.streaming
              ? {
                  ...m,
                  streaming: false,
                  meta: {
                    tokens: event.data.tokens,
                    costUsd: event.data.costUsd,
                    latencyMs: event.data.durationMs ?? undefined,
                  },
                }
              : m,
          ),
        }))
        break
      }
      case 'error': {
        set({ running: false, error: event.error })
        break
      }
      default:
        break
    }
  },

  setWsStatus: (wsStatus) => set({ wsStatus }),
  setProviderOverride: (provider, model = null) =>
    set({ providerOverride: provider, modelOverride: model }),
  clearChat: async () => {
    const { conversationId } = get()
    try {
      await api.clearConversation(conversationId)
    } catch {
      /* pas bloquant */
    }
    set({ chat: [], conversationId: `conv_${uid()}` })
  },
  setToast: (toast) => set({ toast }),
}))
