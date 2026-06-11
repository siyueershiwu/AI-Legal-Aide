import { createParser, type EventSourceMessage } from 'eventsource-parser'
import { getToken } from '@/api/client'
import type { SSEEvent } from '@/types/api'

export interface StreamParams {
  sessionId: string
  message: string
  fileIds: string[]
  signal: AbortSignal
  onText: (delta: string) => void
  onEvent: (evt: SSEEvent) => void
  onDone: (fullContent: string, errorMsg: string | null) => void
  onSessionId: (sessionId: string) => void
}

const HEARTBEAT_TIMEOUT_MS = 60_000  // 60s 无字节视为断流

export function useSSEChat() {
  async function stream(params: StreamParams): Promise<void> {
    const { signal, onText, onEvent, onDone } = params
    const token = getToken()
    const resp = await fetch('/api/v1/chat/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({
        session_id: params.sessionId || null,
        message: params.message,
        file_ids: params.fileIds,
      }),
      signal,
    })

    if (!resp.ok || !resp.body) {
      const text = await resp.text().catch(() => '')
      throw new Error(text || `HTTP ${resp.status}`)
    }

    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    const parser = createParser({
      onEvent: (ev: EventSourceMessage) => handleEvent(ev),
    })

    let full = ''
    let errorMsg: string | null = null

    function handleEvent(ev: EventSourceMessage): void {
      const evt = safeJson(ev.data)
      if (!evt) return
      if (evt.event === 'tool_call' || evt.event === 'tool_result') {
        onEvent(evt as SSEEvent)
      }
      if (typeof evt.content === 'string' && evt.content) {
        full += evt.content
        onText(evt.content)
      }
      if (evt.done) {
        errorMsg = evt.error ?? null
      }
    }

    function safeJson(raw: string): SSEEvent | null {
      try {
        return JSON.parse(raw) as SSEEvent
      } catch {
        return null
      }
    }

    // 心跳 watchdog
    let watchdog: ReturnType<typeof setTimeout> | null = null
    const resetWatchdog = () => {
      if (watchdog) clearTimeout(watchdog)
      watchdog = setTimeout(() => {
        // 60s 无任何字节，主动取消
        void reader.cancel().catch(() => undefined)
      }, HEARTBEAT_TIMEOUT_MS)
    }

    try {
      resetWatchdog()
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        resetWatchdog()
        const chunk = decoder.decode(value, { stream: true })
        parser.feed(chunk)
      }
    } finally {
      if (watchdog) clearTimeout(watchdog)
    }

    onDone(full, errorMsg)
  }

  return { stream }
}
