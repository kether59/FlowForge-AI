import clsx from 'clsx'
import { AlertTriangle, MessagesSquare, Settings2, Activity } from 'lucide-react'
import { useEffect, useState } from 'react'

import { ChatPanel } from './components/ChatPanel'
import { ConfigPanel } from './components/ConfigPanel'
import { DebugPanel } from './components/DebugPanel'
import { FlowCanvas } from './components/FlowCanvas'
import { NodePalette } from './components/NodePalette'
import { TopBar } from './components/TopBar'
import { useWorkflowSocket } from './hooks/useWorkflowSocket'
import { useFlowStore } from './store/useFlowStore'

type Tab = 'config' | 'chat' | 'monitor'

const TABS: { id: Tab; label: string; icon: typeof Settings2 }[] = [
  { id: 'config', label: 'Config', icon: Settings2 },
  { id: 'chat', label: 'Chat', icon: MessagesSquare },
  { id: 'monitor', label: 'Monitor', icon: Activity },
]

export default function App() {
  const bootstrap = useFlowStore((s) => s.bootstrap)
  const loading = useFlowStore((s) => s.loading)
  const error = useFlowStore((s) => s.error)
  const toast = useFlowStore((s) => s.toast)
  const setToast = useFlowStore((s) => s.setToast)
  const workflow = useFlowStore((s) => s.workflow)
  const save = useFlowStore((s) => s.save)
  const selectedNodeId = useFlowStore((s) => s.selectedNodeId)
  const [tab, setTab] = useState<Tab>('config')

  useWorkflowSocket(workflow?.id)

  useEffect(() => {
    void bootstrap()
  }, [bootstrap])

  useEffect(() => {
    if (selectedNodeId) setTab('config')
  }, [selectedNodeId])

  useEffect(() => {
    if (!toast) return
    const timer = setTimeout(() => setToast(null), 3200)
    return () => clearTimeout(timer)
  }, [toast, setToast])

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 's') {
        event.preventDefault()
        void save()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [save])

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-canvas">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-slate-700 border-t-indigo-500" />
          <p className="text-sm text-slate-400">Chargement de FlowForge…</p>
        </div>
      </div>
    )
  }

  if (error && !workflow) {
    return (
      <div className="flex h-screen flex-col items-center justify-center gap-3 bg-canvas px-6 text-center">
        <AlertTriangle className="text-rose-400" />
        <p className="text-sm font-medium text-slate-200">Backend injoignable</p>
        <p className="max-w-md text-xs leading-relaxed text-slate-500">{error}</p>
        <code className="rounded bg-slate-900 px-3 py-1.5 text-[11px] text-slate-400">
          cd backend && uvicorn app.main:app --reload
        </code>
        <button className="btn-primary" onClick={() => void bootstrap()}>
          Réessayer
        </button>
      </div>
    )
  }

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-canvas">
      <TopBar />
      <div className="flex flex-1 overflow-hidden">
        <NodePalette />
        <FlowCanvas />
        <aside className="flex w-[372px] shrink-0 flex-col border-l border-slate-800 bg-panel/60">
          <div className="flex border-b border-slate-800">
            {TABS.map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                onClick={() => setTab(id)}
                className={clsx(
                  'flex flex-1 items-center justify-center gap-1.5 py-2.5 text-[11px] font-medium transition',
                  tab === id
                    ? 'border-b-2 border-indigo-500 bg-slate-900/50 text-indigo-300'
                    : 'border-b-2 border-transparent text-slate-500 hover:text-slate-300',
                )}
              >
                <Icon size={13} /> {label}
              </button>
            ))}
          </div>
          <div className="flex-1 overflow-hidden">
            {tab === 'config' && <ConfigPanel />}
            {tab === 'chat' && <ChatPanel />}
            {tab === 'monitor' && <DebugPanel />}
          </div>
        </aside>
      </div>

      {toast && (
        <div className="pointer-events-none fixed bottom-5 left-1/2 z-50 -translate-x-1/2 rounded-lg border border-slate-700 bg-slate-900/95 px-4 py-2 text-xs text-slate-200 shadow-xl">
          {toast}
        </div>
      )}
    </div>
  )
}
