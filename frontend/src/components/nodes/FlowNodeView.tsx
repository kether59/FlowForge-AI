import { Handle, Position, type NodeProps } from '@xyflow/react'
import clsx from 'clsx'
import type { LucideIcon } from 'lucide-react'
import {
  Braces,
  CircuitBoard,
  Code2,
  Database,
  Flag,
  GitBranch,
  GitMerge,
  Layers3,
  MessageSquare,
  Sparkles,
  Timer,
  TriangleAlert,
  Coins,
} from 'lucide-react'

import type { FlowNodeData } from '../../lib/types'
import { StatusDot } from '../ui'

const ICONS: Record<string, LucideIcon> = {
  chat: MessageSquare,
  flag: Flag,
  database: Database,
  layers: Layers3,
  sparkles: Sparkles,
  'git-branch': GitBranch,
  gate: CircuitBoard,
  merge: GitMerge,
  braces: Braces,
  code: Code2,
}

const STATUS_BORDER: Record<string, string> = {
  idle: 'border-slate-700',
  queued: 'border-sky-500/60',
  running: 'border-amber-400/80 shadow-[0_0_0_1px_rgba(251,191,36,.35)]',
  success: 'border-emerald-500/60',
  error: 'border-rose-500/80',
  skipped: 'border-slate-800 opacity-70',
}

export function FlowNodeView({ data, selected }: NodeProps) {
  const d = data as unknown as FlowNodeData
  const spec = d.spec
  const color = spec?.color ?? '#64748b'
  const Icon = ICONS[spec?.icon ?? ''] ?? CircuitBoard
  const inputs = spec?.inputs ?? []
  const outputs = spec?.outputs ?? []

  return (
    <div
      className={clsx(
        'relative w-[210px] overflow-hidden rounded-xl border bg-panel/95 text-left shadow-lg shadow-black/30 backdrop-blur transition',
        STATUS_BORDER[d.status] ?? 'border-slate-700',
        selected && 'ring-2 ring-indigo-500/70',
      )}
    >
      {/* entrées */}
      {inputs.map((handle, index) => (
        <Handle
          key={handle.id}
          id={handle.id}
          type="target"
          position={Position.Left}
          style={{ top: `${((index + 1) / (inputs.length + 1)) * 100}%` }}
        />
      ))}
      {/* sorties */}
      {outputs.map((handle, index) => (
        <Handle
          key={handle.id}
          id={handle.id}
          type="source"
          position={Position.Right}
          style={{
            top: `${((index + 1) / (outputs.length + 1)) * 100}%`,
            background: handle.id === 'true' ? '#34d399' : handle.id === 'false' ? '#f87171' : undefined,
          }}
        />
      ))}

      <div
        className="flex items-center gap-2 border-b border-slate-800 px-3 py-2"
        style={{ background: `linear-gradient(90deg, ${color}22, transparent)` }}
      >
        <span
          className="flex h-6 w-6 items-center justify-center rounded-md"
          style={{ background: `${color}26`, color }}
        >
          <Icon size={14} />
        </span>
        <span className="flex-1 truncate text-[13px] font-semibold text-slate-100">{d.label}</span>
        <StatusDot status={d.status} />
      </div>

      <div className="px-3 py-2 text-[11px] text-slate-400">
        {spec?.description ? <p className="line-clamp-2 leading-snug">{spec.description}</p> : null}

        <div className="mt-2 flex flex-wrap items-center gap-1.5 text-[10px] text-slate-400">
          {d.nodeType === 'llm' && (
            <>
              <span className="chip">{String(d.config.provider ?? 'mock')}</span>
              <span className="chip">T={String(d.config.temperature ?? 0.7)}</span>
              {d.config.memoryEnabled ? <span className="chip">mémoire</span> : null}
            </>
          )}
          {d.nodeType === 'source' && <span className="chip">{String(d.config.kind ?? 'inline')}</span>}
          {d.nodeType === 'vectorStore' && (
            <>
              <span className="chip">{String(d.config.operation ?? 'index')}</span>
              <span className="chip">{String(d.config.storeId ?? 'default')}</span>
            </>
          )}
          {d.nodeType === 'condition' && <span className="chip">{String(d.config.mode ?? 'expression')}</span>}
          {d.nodeType === 'logicGate' && (
            <span className="chip">{String(d.config.gate ?? 'and').toUpperCase()}</span>
          )}
          {d.nodeType === 'merge' && <span className="chip">{String(d.config.mode ?? 'concat')}</span>}
        </div>

        {(d.latencyMs != null || (d.totalTokens ?? 0) > 0) && (
          <div className="mt-2 flex items-center gap-3 border-t border-slate-800 pt-2 font-mono text-[10px] text-slate-400">
            <span className="inline-flex items-center gap-1">
              <Timer size={10} /> {d.latencyMs != null ? `${Math.round(d.latencyMs)}ms` : '—'}
            </span>
            {(d.totalTokens ?? 0) > 0 && (
              <span className="inline-flex items-center gap-1">
                <Sparkles size={10} /> {d.totalTokens ?? 0} tok
              </span>
            )}
            {!!d.costUsd && (
              <span className="inline-flex items-center gap-1">
                <Coins size={10} /> ${Number(d.costUsd).toFixed(5)}
              </span>
            )}
          </div>
        )}

        {d.error && d.status === 'error' && (
          <div className="mt-2 flex items-start gap-1 rounded bg-rose-950/60 px-2 py-1 text-[10px] text-rose-300">
            <TriangleAlert size={11} className="mt-0.5 shrink-0" />
            <span className="line-clamp-2">{d.error}</span>
          </div>
        )}
      </div>

      {/* labels des handles multi-sorties */}
      {outputs.length > 1 && (
        <div className="pointer-events-none absolute inset-y-0 -right-14 w-14">
          {outputs.map((handle, index) => (
            <span
              key={handle.id}
              className="absolute text-[9px] uppercase tracking-wide text-slate-500"
              style={{ top: `calc(${((index + 1) / (outputs.length + 1)) * 100}% - 6px)` }}
            >
              {handle.label}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}
