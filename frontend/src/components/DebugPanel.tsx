import clsx from 'clsx'
import { ChevronDown, ChevronRight, Clock, Coins, History, Loader2, Sparkles } from 'lucide-react'
import { useEffect, useState } from 'react'

import { api } from '../lib/api'
import type { Execution, NodeUsage } from '../lib/types'
import { useFlowStore } from '../store/useFlowStore'
import { JsonView, StatusDot, formatCost, formatMs } from './ui'

const STATUS_COLORS: Record<string, string> = {
  running: 'text-amber-300',
  success: 'text-emerald-300',
  error: 'text-rose-300',
  skipped: 'text-slate-400',
  queued: 'text-sky-300',
  idle: 'text-slate-400',
}

export function DebugPanel() {
  const execution = useFlowStore((s) => s.execution)
  const running = useFlowStore((s) => s.running)
  const streaming = useFlowStore((s) => s.streaming)
  const workflow = useFlowStore((s) => s.workflow)
  const [expanded, setExpanded] = useState<string | null>(null)
  const [history, setHistory] = useState<Execution[]>([])
  const [pastExecution, setPastExecution] = useState<Execution | null>(null)

  const loadHistory = async () => {
    if (!workflow) return
    try {
      setHistory(await api.executions(workflow.id))
    } catch {
      setHistory([])
    }
  }

  useEffect(() => {
    loadHistory()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workflow?.id, execution?.id])

  const shown = pastExecution ?? execution

  const openPast = async (runId: string) => {
    const ex = await api.execution(runId).catch(() => null)
    if (ex) setPastExecution(ex)
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2 border-b border-slate-800 px-3 py-2">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
          Monitor
        </span>
        {running && <Loader2 size={12} className="animate-spin text-amber-400" />}
        <button className="btn-ghost ml-auto !px-2 !py-1 text-[11px]" onClick={loadHistory}>
          <History size={12} /> Historique
        </button>
      </div>

      {pastExecution && (
        <div className="flex items-center gap-2 border-b border-slate-800 bg-indigo-950/40 px-3 py-1.5 text-[11px] text-indigo-300">
          Exécution historique · {pastExecution.id}
          <button className="ml-auto text-slate-400 hover:text-slate-200" onClick={() => setPastExecution(null)}>
            revenir au live
          </button>
        </div>
      )}

      {!shown ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-2 px-6 text-center">
          <p className="text-sm text-slate-300">Aucune exécution</p>
          <p className="text-xs leading-relaxed text-slate-500">
            Lancez le workflow depuis le chat pour voir le statut, la latence, les tokens et les
            payloads de chaque bloc.
          </p>
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto">
          <div className="grid grid-cols-2 gap-2 border-b border-slate-800 px-3 py-3 text-[11px] sm:grid-cols-4">
            <Metric label="Statut">
              <span className={clsx('inline-flex items-center gap-1.5 font-medium', STATUS_COLORS[shown.status])}>
                <StatusDot status={shown.status} /> {shown.status}
              </span>
            </Metric>
            <Metric label="Durée">
              <span className="inline-flex items-center gap-1 text-slate-200">
                <Clock size={11} /> {formatMs(shown.durationMs)}
              </span>
            </Metric>
            <Metric label="Tokens">
              <span className="inline-flex items-center gap-1 text-slate-200">
                <Sparkles size={11} /> {shown.tokens}
              </span>
            </Metric>
            <Metric label="Coût estimé">
              <span className="inline-flex items-center gap-1 text-slate-200">
                <Coins size={11} /> {formatCost(shown.costUsd)}
              </span>
            </Metric>
          </div>

          {shown.error && (
            <div className="mx-3 mt-3 rounded-lg border border-rose-900/70 bg-rose-950/40 px-2.5 py-2 text-[11px] leading-relaxed text-rose-300">
              {shown.error}
            </div>
          )}

          <div className="px-2 py-2">
            {shown.nodes.map((usage) => (
              <NodeRow
                key={usage.nodeId}
                usage={usage}
                expanded={expanded === usage.nodeId}
                liveTokens={streaming[usage.nodeId]}
                onToggle={() =>
                  setExpanded((current) => (current === usage.nodeId ? null : usage.nodeId))
                }
              />
            ))}
          </div>

          <div className="border-t border-slate-800 px-3 py-3">
            <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
              Sortie finale
            </p>
            <JsonView
              value={
                typeof shown.finalOutput === 'string'
                  ? shown.finalOutput
                  : shown.finalOutput ?? '(vide)'
              }
            />
          </div>

          <div className="border-t border-slate-800 px-3 py-3">
            <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
              Exécutions récentes
            </p>
            <div className="space-y-1">
              {history.length === 0 && <p className="text-[11px] text-slate-500">Aucune exécution.</p>}
              {history.slice(0, 12).map((run) => (
                <button
                  key={run.id}
                  onClick={() => openPast(run.id)}
                  className="flex w-full items-center gap-2 rounded-md border border-slate-800 bg-slate-900/50 px-2 py-1.5 text-left text-[11px] text-slate-300 hover:border-slate-700"
                >
                  <StatusDot status={run.status} />
                  <span className="font-mono text-[10px] text-slate-500">{run.id.slice(0, 12)}</span>
                  <span className="ml-auto text-slate-400">{formatMs(run.durationMs)}</span>
                  <span className="text-slate-500">{run.tokens} tok</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function Metric({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900/50 px-2 py-1.5">
      <p className="text-[9px] uppercase tracking-wider text-slate-500">{label}</p>
      <div className="mt-0.5 text-[12px]">{children}</div>
    </div>
  )
}

function NodeRow({
  usage,
  expanded,
  onToggle,
  liveTokens,
}: {
  usage: NodeUsage
  expanded: boolean
  onToggle: () => void
  liveTokens?: string
}) {
  const Chevron = expanded ? ChevronDown : ChevronRight
  return (
    <div className="mb-1 overflow-hidden rounded-lg border border-slate-800 bg-slate-900/40">
      <button onClick={onToggle} className="flex w-full items-center gap-2 px-2 py-1.5 text-left hover:bg-slate-800/40">
        <Chevron size={12} className="text-slate-500" />
        <StatusDot status={usage.status} />
        <span className="truncate text-[11px] font-medium text-slate-200">
          {usage.label || usage.nodeId}
        </span>
        <span className="ml-auto flex items-center gap-2 font-mono text-[10px] text-slate-500">
          {usage.totalTokens > 0 && <span className="text-indigo-300">{usage.totalTokens} tok</span>}
          <span>{formatMs(usage.latencyMs)}</span>
        </span>
      </button>
      {expanded && (
        <div className="space-y-2 border-t border-slate-800 px-2 py-2">
          {usage.error && (
            <p className="rounded bg-rose-950/50 px-2 py-1 text-[10px] leading-relaxed text-rose-300">
              {usage.error}
            </p>
          )}
          {liveTokens && (
            <div>
              <p className="mb-1 text-[9px] uppercase tracking-wider text-slate-500">Flux temps réel</p>
              <pre className="max-h-32 overflow-auto whitespace-pre-wrap rounded bg-slate-950/70 p-2 font-mono text-[10px] text-emerald-300">
                {liveTokens}
              </pre>
            </div>
          )}
          <details>
            <summary className="cursor-pointer text-[10px] uppercase tracking-wider text-slate-500">
              Entrée
            </summary>
            <JsonView value={usage.input} />
          </details>
          <details open={!liveTokens}>
            <summary className="cursor-pointer text-[10px] uppercase tracking-wider text-slate-500">
              Sortie
            </summary>
            <JsonView value={usage.output} />
          </details>
          {usage.meta && Object.keys(usage.meta).length > 0 && (
            <details>
              <summary className="cursor-pointer text-[10px] uppercase tracking-wider text-slate-500">
                Métadonnées
              </summary>
              <JsonView value={usage.meta} />
            </details>
          )}
          <p className="font-mono text-[9px] text-slate-600">
            {usage.nodeId} · {usage.nodeType} · {usage.promptTokens}p / {usage.completionTokens}c ·{' '}
            {formatCost(usage.costUsd)}
          </p>
        </div>
      )}
    </div>
  )
}
