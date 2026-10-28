import clsx from 'clsx'
import {
  CheckCircle2,
  Copy,
  FilePlus2,
  Play,
  Save,
  Trash2,
  Workflow as WorkflowIcon,
  Wifi,
  WifiOff,
} from 'lucide-react'
import { useState } from 'react'

import { useFlowStore } from '../store/useFlowStore'

export function TopBar() {
  const workflows = useFlowStore((s) => s.workflows)
  const workflow = useFlowStore((s) => s.workflow)
  const dirty = useFlowStore((s) => s.dirty)
  const saving = useFlowStore((s) => s.saving)
  const wsStatus = useFlowStore((s) => s.wsStatus)
  const running = useFlowStore((s) => s.running)
  const lastPrompt = useFlowStore((s) => s.chat.filter((m) => m.role === 'user').at(-1)?.content)
  const { openWorkflow, renameWorkflow, save, validate, createWorkflow, duplicateWorkflow, deleteWorkflow, run } =
    useFlowStore()
  const [confirmDelete, setConfirmDelete] = useState(false)

  return (
    <header className="flex h-14 shrink-0 items-center gap-3 border-b border-slate-800 bg-panel/80 px-4">
      <div className="flex items-center gap-2">
        <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-fuchsia-600 text-white">
          <WorkflowIcon size={17} />
        </span>
        <div className="leading-tight">
          <p className="text-sm font-semibold text-slate-100">FlowForge AI</p>
          <p className="text-[10px] text-slate-500">Orchestrateur de processus IA</p>
        </div>
      </div>

      <div className="mx-2 h-7 w-px bg-slate-800" />

      <select
        className="input h-8 w-auto max-w-[220px] text-xs"
        value={workflow?.id ?? ''}
        onChange={(e) => void openWorkflow(e.target.value)}
      >
        {workflows.map((w) => (
          <option key={w.id} value={w.id}>
            {w.name}
          </option>
        ))}
      </select>

      <input
        className="h-8 w-[260px] rounded-lg border border-transparent bg-transparent px-2 text-sm font-medium text-slate-200 outline-none hover:border-slate-800 focus:border-indigo-600"
        value={workflow?.name ?? ''}
        onChange={(e) => renameWorkflow(e.target.value)}
        placeholder="Nom du workflow"
      />

      <span
        className={clsx(
          'chip',
          dirty ? 'bg-amber-500/15 text-amber-300' : 'bg-emerald-500/15 text-emerald-300',
        )}
      >
        {dirty ? 'modifications non enregistrées' : 'à jour'}
      </span>

      <div className="ml-auto flex items-center gap-1.5">
        <span
          className={clsx(
            'chip gap-1',
            wsStatus === 'open'
              ? 'bg-emerald-500/10 text-emerald-300'
              : wsStatus === 'connecting'
                ? 'bg-amber-500/10 text-amber-300'
                : 'bg-rose-500/10 text-rose-300',
          )}
          title="Canal WebSocket de streaming"
        >
          {wsStatus === 'open' ? <Wifi size={11} /> : <WifiOff size={11} />} ws
        </span>

        <button className="btn-ghost" onClick={() => void validate()} title="Valider le DAG">
          <CheckCircle2 size={14} /> Valider
        </button>
        <button className="btn-ghost" onClick={() => void save()} disabled={saving} title="Enregistrer (Ctrl+S)">
          <Save size={14} /> {saving ? 'Enregistrement…' : 'Enregistrer'}
        </button>
        <button
          className="btn-primary"
          disabled={running}
          onClick={() => void run(lastPrompt || 'Présente le workflow en trois points.')}
          title="Exécuter sans passer par le chat"
        >
          <Play size={14} /> {running ? 'Exécution…' : 'Exécuter'}
        </button>

        <div className="mx-1 h-7 w-px bg-slate-800" />

        <button className="btn-ghost !px-2" onClick={() => void createWorkflow()} title="Nouveau workflow">
          <FilePlus2 size={14} />
        </button>
        <button className="btn-ghost !px-2" onClick={() => void duplicateWorkflow()} title="Dupliquer">
          <Copy size={14} />
        </button>
        {confirmDelete ? (
          <button
            className="btn-danger !px-2 text-[11px]"
            onClick={() => {
              void deleteWorkflow()
              setConfirmDelete(false)
            }}
            onBlur={() => setConfirmDelete(false)}
          >
            Confirmer
          </button>
        ) : (
          <button
            className="btn-ghost !px-2 hover:!bg-rose-950/60 hover:!text-rose-300"
            onClick={() => setConfirmDelete(true)}
            title="Supprimer"
          >
            <Trash2 size={14} />
          </button>
        )}
      </div>
    </header>
  )
}
