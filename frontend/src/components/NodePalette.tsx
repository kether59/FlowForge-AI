import clsx from 'clsx'
import { Search } from 'lucide-react'
import { useMemo, useState } from 'react'

import type { NodeTypeSpec } from '../lib/types'
import { useFlowStore } from '../store/useFlowStore'

const CATEGORY_LABELS: Record<string, string> = {
  io: 'Entrées / Sorties',
  data: 'Données & RAG',
  ai: 'IA & Assistant',
  logic: 'Logique & Contrôle',
  code: 'Programmable',
}

const CATEGORY_COLORS: Record<string, string> = {
  io: 'text-sky-400',
  data: 'text-amber-400',
  ai: 'text-pink-400',
  logic: 'text-violet-400',
  code: 'text-teal-400',
}

export function NodePalette() {
  const specs = useFlowStore((s) => s.specs)
  const addNode = useFlowStore((s) => s.addNode)
  const [query, setQuery] = useState('')

  const grouped = useMemo(() => {
    const filtered = specs.filter(
      (s) =>
        !query ||
        s.label.toLowerCase().includes(query.toLowerCase()) ||
        s.description.toLowerCase().includes(query.toLowerCase()),
    )
    return filtered.reduce<Record<string, NodeTypeSpec[]>>((acc, spec) => {
      acc[spec.category] = [...(acc[spec.category] ?? []), spec]
      return acc
    }, {})
  }, [specs, query])

  const onDragStart = (event: React.DragEvent, type: string) => {
    event.dataTransfer.setData('application/flowforge-node', type)
    event.dataTransfer.effectAllowed = 'move'
  }

  return (
    <aside className="flex w-[248px] shrink-0 flex-col border-r border-slate-800 bg-panel/60">
      <div className="border-b border-slate-800 px-3 py-3">
        <div className="relative">
          <Search size={13} className="absolute left-2.5 top-2.5 text-slate-500" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Rechercher un bloc…"
            className="input pl-8 text-xs"
          />
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-2 py-3">
        {Object.entries(grouped).map(([category, items]) => (
          <div key={category} className="mb-4">
            <p
              className={clsx(
                'mb-1.5 px-1 text-[10px] font-semibold uppercase tracking-widest',
                CATEGORY_COLORS[category] ?? 'text-slate-500',
              )}
            >
              {CATEGORY_LABELS[category] ?? category}
            </p>
            {items.map((spec) => (
              <div
                key={spec.type}
                draggable
                onDragStart={(e) => onDragStart(e, spec.type)}
                onDoubleClick={() =>
                  addNode(spec.type, { x: 120 + Math.random() * 320, y: 80 + Math.random() * 320 })
                }
                className="group mb-1.5 cursor-grab rounded-lg border border-slate-800 bg-slate-900/60 px-2.5 py-2 transition hover:border-slate-600 hover:bg-slate-800/60 active:cursor-grabbing"
                title={spec.description}
              >
                <div className="flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full" style={{ background: spec.color }} />
                  <span className="text-xs font-medium text-slate-200">{spec.label}</span>
                </div>
                <p className="mt-0.5 line-clamp-2 pl-4 text-[10px] leading-snug text-slate-500">
                  {spec.description}
                </p>
              </div>
            ))}
          </div>
        ))}
        <p className="px-1 text-[10px] leading-relaxed text-slate-600">
          Glissez un bloc sur le canvas (ou double-cliquez).
        </p>
      </div>
    </aside>
  )
}
