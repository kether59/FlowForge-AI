import clsx from 'clsx'
import { Eraser, Loader2, Send, Sparkles, User } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import { useFlowStore } from '../store/useFlowStore'
import { Select, formatCost, formatMs } from './ui'

export function ChatPanel() {
  const chat = useFlowStore((s) => s.chat)
  const run = useFlowStore((s) => s.run)
  const running = useFlowStore((s) => s.running)
  const clearChat = useFlowStore((s) => s.clearChat)
  const providers = useFlowStore((s) => s.providers)
  const providerOverride = useFlowStore((s) => s.providerOverride)
  const modelOverride = useFlowStore((s) => s.modelOverride)
  const setProviderOverride = useFlowStore((s) => s.setProviderOverride)
  const nodes = useFlowStore((s) => s.nodes)
  const conversationId = useFlowStore((s) => s.conversationId)
  const [prompt, setPrompt] = useState('')
  const scroller = useRef<HTMLDivElement>(null)

  const inputNode = nodes.find((n) => n.data.nodeType === 'input')
  const placeholder =
    (inputNode?.data.config.placeholder as string) || 'Posez votre question…'

  useEffect(() => {
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: 'smooth' })
  }, [chat])

  const submit = () => {
    const value = prompt.trim()
    if (!value || running) return
    setPrompt('')
    void run(value)
  }

  const providerList = providers?.providers ?? {}
  const models = providerOverride ? providerList[providerOverride]?.models ?? [] : []

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2 border-b border-slate-800 px-3 py-2">
        <Select
          value={providerOverride ?? ''}
          onChange={(value) => setProviderOverride(value || null, null)}
          options={[
            { value: '', label: 'Provider du workflow' },
            ...Object.entries(providerList).map(([key, info]) => ({
              value: key,
              label: info.label,
            })),
          ]}
        />
        <button className="btn-ghost !px-2 !py-1" onClick={() => clearChat()} title="Réinitialiser la mémoire">
          <Eraser size={13} />
        </button>
      </div>

      {providerOverride && (
        <div className="border-b border-slate-800 px-3 py-2">
          <Select
            value={modelOverride ?? models[0] ?? ''}
            onChange={(model) => setProviderOverride(providerOverride, model)}
            options={models.map((m) => ({ value: m, label: m }))}
          />
        </div>
      )}

      <div ref={scroller} className="flex-1 space-y-3 overflow-y-auto px-3 py-3">
        {chat.length === 0 && (
          <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-3 text-[11px] leading-relaxed text-slate-400">
            <p className="mb-1 flex items-center gap-1.5 font-medium text-slate-200">
              <Sparkles size={12} className="text-indigo-400" /> Chat de test
            </p>
            Le message est injecté dans le nœud <span className="font-mono text-indigo-300">Chat Input</span>,
            puis traverse le graphe. Les tokens du LLM arrivent en streaming via WebSocket.
            <p className="mt-2 text-slate-500">
              Conversation : <span className="font-mono">{conversationId}</span> (mémoire côté serveur)
            </p>
          </div>
        )}

        {chat.map((message) => (
          <div
            key={message.id}
            className={clsx('flex gap-2', message.role === 'user' ? 'justify-end' : 'justify-start')}
          >
            {message.role === 'assistant' && (
              <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-indigo-600/20 text-indigo-300">
                <Sparkles size={12} />
              </span>
            )}
            <div
              className={clsx(
                'max-w-[85%] rounded-xl px-3 py-2 text-[12px] leading-relaxed',
                message.role === 'user'
                  ? 'bg-indigo-600 text-white'
                  : message.meta?.error
                    ? 'border border-rose-900/60 bg-rose-950/40 text-rose-200'
                    : 'border border-slate-800 bg-slate-900/70 text-slate-200',
              )}
            >
              <p className="whitespace-pre-wrap">
                {message.content}
                {message.streaming && <span className="ml-0.5 inline-block h-3 w-1.5 animate-pulse bg-indigo-400" />}
              </p>
              {message.meta && (message.meta.tokens || message.meta.latencyMs) && !message.streaming ? (
                <p className="mt-1.5 flex flex-wrap gap-2 border-t border-white/10 pt-1 font-mono text-[9px] text-slate-400">
                  {message.meta.tokens ? <span>{message.meta.tokens} tokens</span> : null}
                  {message.meta.costUsd !== undefined ? <span>{formatCost(message.meta.costUsd)}</span> : null}
                  {message.meta.latencyMs ? <span>{formatMs(message.meta.latencyMs)}</span> : null}
                  {message.meta.model ? <span>{message.meta.model}</span> : null}
                </p>
              ) : null}
            </div>
            {message.role === 'user' && (
              <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-slate-800 text-slate-300">
                <User size={12} />
              </span>
            )}
          </div>
        ))}
      </div>

      <div className="border-t border-slate-800 p-3">
        <div className="flex items-end gap-2">
          <textarea
            className="input max-h-32 min-h-[42px] resize-none py-2 text-[12px]"
            rows={2}
            placeholder={placeholder}
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                submit()
              }
            }}
          />
          <button className="btn-primary h-[42px] px-3" onClick={submit} disabled={running || !prompt.trim()}>
            {running ? <Loader2 size={15} className="animate-spin" /> : <Send size={15} />}
          </button>
        </div>
        <p className="mt-1.5 text-[10px] text-slate-600">
          Entrée pour envoyer · Maj+Entrée pour un retour à la ligne
        </p>
      </div>
    </div>
  )
}
