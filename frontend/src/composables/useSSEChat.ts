import { createParser, type EventSourceMessage } from 'eventsource-parser'
import { getToken } from '@/api/client'
import type { KnowledgeSource, SSEEvent } from '@/types/api'

export interface StreamParams {
  sessionId: string
  message: string
  fileIds: string[]
  signal: AbortSignal
  onText: (delta: string) => void
  onEvent: (evt: SSEEvent) => void
  onDone: (fullContent: string, errorMsg: string | null) => void
  onSessionId: (sessionId: string) => void
  onSources?: (sources: KnowledgeSource[]) => void
}

// 心跳超时：kb_search 触发的双轮 LLM 链路（首轮 tool_call → embed_query
// CPU 跑 → ChromaDB → 关联拉取 → 第二轮模型）慢的时候中间会有 30s+ 完全
// 静默；后端会每 15s 发一行 SSE 注释行（": ping\n\n"）重置这个计时器。
// 60s 偏紧，给 90s 当兜底——超过这个时间没人 ping 才是真断流。
const HEARTBEAT_TIMEOUT_MS = 90_000

export function useSSEChat() {
  async function stream(params: StreamParams): Promise<void> {
    const { signal, onText, onEvent, onDone, onSessionId, onSources } = params
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
      // 后端首帧会发 session_id（首次提问时是后端新建的），前端必须记下
      // 才能让同一对话内的后续提问归属同一条历史记录
      if (typeof evt.session_id === 'string' && evt.session_id) {
        onSessionId(evt.session_id)
      }
      if (evt.event === 'tool_call' || evt.event === 'tool_result') {
        onEvent(evt as SSEEvent)
      }
      if (evt.event === 'sources' && Array.isArray(evt.sources) && onSources) {
        onSources(evt.sources as KnowledgeSource[])
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
