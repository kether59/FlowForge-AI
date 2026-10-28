import type {
  Execution,
  NodeTypeSpec,
  ProvidersResponse,
  Workflow,
  WorkflowSummary,
} from './types'

const BASE = '/api'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: init?.body instanceof FormData ? undefined : { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body.detail ?? body.error ?? JSON.stringify(body)
    } catch {
      if (res.status === 413) {
        detail = 'Fichier trop volumineux : la limite d’import du serveur est dépassée.'
      }
    }
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
  }
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

export const api = {
  health: () => request<{ status: string }>('/health'),
  nodeTypes: () => request<NodeTypeSpec[]>('/node-types'),
  providers: () => request<ProvidersResponse>('/providers'),
  testProvider: (provider: string, model: string, prompt = 'Dis bonjour en une phrase.') =>
    request<{ ok: boolean; text?: string; error?: string }>('/providers/test', {
      method: 'POST',
      body: JSON.stringify({ provider, model, prompt }),
    }),

  listWorkflows: () => request<WorkflowSummary[]>('/workflows'),
  getWorkflow: (id: string) => request<Workflow>(`/workflows/${id}`),
  createWorkflow: (name?: string) =>
    request<Workflow>('/workflows', { method: 'POST', body: JSON.stringify({ name }) }),
  saveWorkflow: (wf: Workflow) =>
    request<Workflow>(`/workflows/${wf.id}`, { method: 'PUT', body: JSON.stringify(wf) }),
  duplicateWorkflow: (id: string) =>
    request<Workflow>(`/workflows/${id}/duplicate`, { method: 'POST' }),
  deleteWorkflow: (id: string) =>
    request<{ deleted: boolean }>(`/workflows/${id}`, { method: 'DELETE' }),
  validate: (wf: Workflow) =>
    request<{ valid: boolean; levels?: string[][]; error?: string }>('/workflows/validate', {
      method: 'POST',
      body: JSON.stringify(wf),
    }),

  run: (id: string, payload: { input: Record<string, any>; conversationId?: string; provider?: string; model?: string }) =>
    request<Execution>(`/workflows/${id}/run`, { method: 'POST', body: JSON.stringify(payload) }),
  executions: (workflowId?: string) =>
    request<Execution[]>(`/executions${workflowId ? `?workflowId=${workflowId}` : ''}`),
  execution: (id: string) => request<Execution>(`/executions/${id}`),
  clearConversation: (conversationId: string) =>
    request<{ cleared: boolean }>(`/conversations/${encodeURIComponent(conversationId)}`, {
      method: 'DELETE',
    }),

  uploads: () => request<{ id: string; name: string; size: number }[]>('/sources/uploads'),
  uploadSource: async (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return request<{ document: { id: string; name: string; text: string }; chars: number }>(
      '/sources/upload',
      { method: 'POST', body: form },
    )
  },
  importDrive: (payload: Record<string, any>) =>
    request<{ mode: Record<string, any>; documents: any[] }>('/sources/drive', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  importConfluence: (payload: Record<string, any>) =>
    request<{ mode: Record<string, any>; documents: any[] }>('/sources/confluence', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  vectorStores: () => request<{ storeId: string; vectors: number }[]>('/vectorstores'),
  clearVectorStore: (storeId: string) =>
    request<{ cleared: boolean }>(`/vectorstores/${storeId}`, { method: 'DELETE' }),
  queryVectorStore: (storeId: string, q: string) =>
    request<{ storeId: string; vectors: number; matches?: any[] }>(
      `/vectorstores/${storeId}?q=${encodeURIComponent(q)}`,
    ),
}

export function wsUrl(path: string): string {
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
  return `${proto}://${window.location.host}${path}`
}
