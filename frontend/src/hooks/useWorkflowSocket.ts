import { useEffect, useRef } from 'react'

import { wsUrl } from '../lib/api'
import type { WsEvent } from '../lib/types'
import { useFlowStore } from '../store/useFlowStore'

/** Ouvre un WebSocket sur le canal d'exécution du workflow et alimente le store. */
export function useWorkflowSocket(workflowId: string | undefined) {
  const applyEvent = useFlowStore((s) => s.applyEvent)
  const setWsStatus = useFlowStore((s) => s.setWsStatus)
  const socketRef = useRef<WebSocket | null>(null)
  const retryRef = useRef<number>(0)

  useEffect(() => {
    if (!workflowId) return
    let closed = false
    let timer: ReturnType<typeof setTimeout> | undefined

    const connect = () => {
      setWsStatus('connecting')
      const ws = new WebSocket(wsUrl(`/ws/workflows/${workflowId}`))
      socketRef.current = ws

      ws.onopen = () => {
        retryRef.current = 0
        setWsStatus('open')
      }
      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data) as WsEvent
          if (payload.type === 'connected') return
          applyEvent(payload)
        } catch {
          /* ignore */
        }
      }
      ws.onclose = () => {
        setWsStatus('closed')
        if (closed) return
        retryRef.current = Math.min(retryRef.current + 1, 6)
        timer = setTimeout(connect, 500 * 2 ** retryRef.current)
      }
      ws.onerror = () => ws.close()
    }

    connect()

    return () => {
      closed = true
      if (timer) clearTimeout(timer)
      socketRef.current?.close()
      setWsStatus('closed')
    }
  }, [workflowId, applyEvent, setWsStatus])
}
