import clsx from 'clsx'
import type { ReactNode } from 'react'

export function Field({
  label,
  hint,
  children,
}: {
  label: string
  hint?: ReactNode
  children: ReactNode
}) {
  return (
    <div className="mb-3">
      <label className="label">{label}</label>
      {children}
      {hint ? <p className="mt-1 text-[11px] leading-relaxed text-slate-500">{hint}</p> : null}
    </div>
  )
}

export function TextInput({
  value,
  onChange,
  placeholder,
  mono,
  type = 'text',
}: {
  value: string | number
  onChange: (value: string) => void
  placeholder?: string
  mono?: boolean
  type?: string
}) {
  return (
    <input
      className={clsx('input', mono && 'font-mono text-xs')}
      value={value ?? ''}
      type={type}
      placeholder={placeholder}
      onChange={(e) => onChange(e.target.value)}
    />
  )
}

export function TextArea({
  value,
  onChange,
  rows = 4,
  mono,
  placeholder,
}: {
  value: string
  onChange: (value: string) => void
  rows?: number
  mono?: boolean
  placeholder?: string
}) {
  return (
    <textarea
      className={clsx('input resize-y leading-relaxed', mono && 'font-mono text-xs')}
      rows={rows}
      value={value ?? ''}
      placeholder={placeholder}
      onChange={(e) => onChange(e.target.value)}
    />
  )
}

export function Select({
  value,
  onChange,
  options,
}: {
  value: string
  onChange: (value: string) => void
  options: { value: string; label: string; disabled?: boolean }[]
}) {
  return (
    <select className="input" value={value} onChange={(e) => onChange(e.target.value)}>
      {options.map((o) => (
        <option key={o.value} value={o.value} disabled={o.disabled}>
          {o.label}
        </option>
      ))}
    </select>
  )
}

export function Toggle({
  checked,
  onChange,
  label,
}: {
  checked: boolean
  onChange: (checked: boolean) => void
  label: string
}) {
  return (
    <button
      type="button"
      onClick={() => onChange(!checked)}
      className="mb-3 flex w-full items-center justify-between rounded-lg border border-slate-800 bg-slate-900/60 px-3 py-2 text-sm text-slate-300 hover:border-slate-700"
    >
      <span>{label}</span>
      <span
        className={clsx(
          'relative h-5 w-9 rounded-full transition',
          checked ? 'bg-indigo-600' : 'bg-slate-700',
        )}
      >
        <span
          className={clsx(
            'absolute top-0.5 h-4 w-4 rounded-full bg-white transition-all',
            checked ? 'left-4' : 'left-0.5',
          )}
        />
      </span>
    </button>
  )
}

export function Slider({
  value,
  onChange,
  min,
  max,
  step,
  suffix,
}: {
  value: number
  onChange: (value: number) => void
  min: number
  max: number
  step: number
  suffix?: string
}) {
  return (
    <div className="flex items-center gap-3">
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="h-1.5 flex-1 cursor-pointer appearance-none rounded-full bg-slate-700 accent-indigo-500"
      />
      <span className="w-14 rounded bg-slate-800 px-1.5 py-0.5 text-center font-mono text-xs text-slate-300">
        {value}
        {suffix ?? ''}
      </span>
    </div>
  )
}

const STATUS_STYLES: Record<string, string> = {
  idle: 'bg-slate-600',
  queued: 'bg-sky-400',
  running: 'bg-amber-400 animate-pulseSoft',
  success: 'bg-emerald-500',
  error: 'bg-rose-500',
  skipped: 'bg-slate-500',
}

export function StatusDot({ status }: { status: string }) {
  return <span className={clsx('inline-block h-2 w-2 rounded-full', STATUS_STYLES[status] ?? 'bg-slate-600')} />
}

export function JsonView({ value }: { value: unknown }) {
  if (value === null || value === undefined) return <span className="text-slate-500">—</span>
  return (
    <pre className="max-h-64 overflow-auto rounded-lg border border-slate-800 bg-slate-950/70 p-2 font-mono text-[11px] leading-relaxed text-slate-300">
      {JSON.stringify(value, null, 2)}
    </pre>
  )
}

export function formatMs(ms?: number | null): string {
  if (ms === null || ms === undefined) return '—'
  if (ms < 1000) return `${Math.round(ms)} ms`
  return `${(ms / 1000).toFixed(2)} s`
}

export function formatCost(cost?: number | null): string {
  if (!cost) return '$0'
  return cost < 0.01 ? `$${cost.toFixed(5)}` : `$${cost.toFixed(3)}`
}
