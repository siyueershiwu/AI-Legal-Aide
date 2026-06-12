import { defineStore } from 'pinia'
import { computed, ref, shallowRef } from 'vue'
import * as sessionsApi from '@/api/sessions'
import { stopChat as apiStopChat } from '@/api/chat'
import { useSSEChat } from '@/composables/useSSEChat'
import type { ChatSession, Message, SessionDetail } from '@/types/api'

export const useChatStore = defineStore('chat', () => {
  const messages = ref<Message[]>([])
  // O(1) 索引：id -> Message。用 shallowRef 避免大消息触发深度响应
  const messagesById = ref<Map<string, Message>>(new Map())
  const currentSessionId = ref<string>('')
  const isStreaming = ref(false)
  const sessions = ref<ChatSession[]>([])

  let abortController: AbortController | null = null
  let activeAiMessageId: string | null = null

  const sse = useSSEChat()

  const activeAiMessage = computed<Message | null>(
    () => (activeAiMessageId ? messagesById.value.get(activeAiMessageId) ?? null : null),
  )

  function genId(): string {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
      const r = (Math.random() * 16) | 0
      const v = c === 'x' ? r : (r & 0x3) | 0x8
      return v.toString(16)
    })
  }

  function rebuildIndex(): void {
    const map = new Map<string, Message>()
    for (const m of messages.value) map.set(m.id, m)
    messagesById.value = map
  }

  function resetSession(): void {
    messages.value = []
    rebuildIndex()
    currentSessionId.value = ''
  }

  async function loadSessions(): Promise<void> {
    try {
      const data = await sessionsApi.listSessions()
      sessions.value = data.sessions
    } catch (e) {
      console.error('loadSessions failed', e)
      sessions.value = []
    }
  }

  async function selectSession(sessionId: string): Promise<void> {
    try {
      const detail: SessionDetail = await sessionsApi.getSession(sessionId)
      currentSessionId.value = sessionId
      messages.value = detail.messages.map((m) => ({
        ...m,
        displayedContent: m.content,
        isStreaming: false,
        loading: false,
      }))
      rebuildIndex()
    } catch (e) {
      console.error('selectSession failed', e)
    }
  }

  async function deleteSession(sessionId: string): Promise<void> {
    try {
      await sessionsApi.deleteSession(sessionId)
      if (sessionId === currentSessionId.value) {
        resetSession()
      }
      await loadSessions()
    } catch (e) {
      console.error('deleteSession failed', e)
    }
  }

  async function clearCurrentMessages(): Promise<void> {
    if (!currentSessionId.value) {
      messages.value = []
      rebuildIndex()
      return
    }
    try {
      await sessionsApi.clearSessionMessages(currentSessionId.value)
      messages.value = []
      rebuildIndex()
    } catch (e) {
      console.error('clearCurrentMessages failed', e)
    }
  }

  async function pinSession(sessionId: string): Promise<void> {
    try {
      await sessionsApi.pinSession(sessionId)
      await loadSessions()
    } catch (e) {
      console.error('pinSession failed', e)
    }
  }

  async function renameSession(sessionId: string, title: string): Promise<void> {
    try {
      await sessionsApi.renameSession(sessionId, title)
      await loadSessions()
    } catch (e) {
      console.error('renameSession failed', e)
    }
  }

  function appendUserMessage(
    text: string,
    files: Array<{ id: string; url: string; type: string; name: string }>,
  ): void {
    const imageUrl = files.find((f) => f.type.startsWith('image/'))?.url
    const msg: Message = {
      id: genId(),
      role: 'user',
      content: text,
      files,
      image: imageUrl,
      created_at: new Date().toISOString(),
    }
    messages.value.push(msg)
    messagesById.value.set(msg.id, msg)
  }

  function appendAssistantPlaceholder(): string {
    const id = genId()
    activeAiMessageId = id
    const msg: Message = {
      id,
      role: 'assistant',
      content: '',
      displayedContent: '',
      isStreaming: true,
      loading: true,
      created_at: new Date().toISOString(),
    }
    messages.value.push(msg)
    messagesById.value.set(id, msg)
    return id
  }

  function patchAssistant(content: string, done: boolean, error: string | null): void {
    if (!activeAiMessageId) return
    const msg = messages.value.find(m => m.id === activeAiMessageId)
    if (!msg) return
    msg.displayedContent = content
    msg.content = error ? `${content}\n\n[错误] ${error}` : content
    msg.loading = !done
    msg.isStreaming = !done
  }

  // RAG 引用来源绑定：把 kb_search 的检索结果附到当前正在流的 AI 消息上
  function attachSources(sources: import('@/types/api').KnowledgeSource[]): void {
    if (!activeAiMessageId) return
    const msg = messages.value.find(m => m.id === activeAiMessageId)
    if (!msg) return
    // 后端可能多轮 kb_search → 累加而不是覆盖
    const existing = msg.sources ?? []
    // 用 chunk_id + title 去重，避免重复
    const seen = new Set(existing.map((s) => `${s.title}|${s.snippet.slice(0, 60)}`))
    const merged = [...existing]
    for (const s of sources) {
      const k = `${s.title}|${s.snippet.slice(0, 60)}`
      if (!seen.has(k)) {
        seen.add(k)
        merged.push(s)
      }
    }
    msg.sources = merged
  }

  async function sendMessage(
    text: string,
    fileIds: string[],
    files: Array<{ id: string; url: string; type: string; name: string }> = [],
  ): Promise<void> {
    if (isStreaming.value) return
    if (!text.trim() && fileIds.length === 0) return

    const finalText = text.trim() || '发送附件'
    appendUserMessage(finalText, files)

    const aiId = appendAssistantPlaceholder()
    isStreaming.value = true

    abortController = new AbortController()
    try {
      await sse.stream({
        sessionId: currentSessionId.value,
        message: finalText,
        fileIds,
        signal: abortController.signal,
        onText: (delta) => {
          // 直接从 messages 数组找（响应式数组中的对象是 reactive 的）
          const msg = messages.value.find(m => m.id === aiId)
          if (msg) {
            msg.displayedContent = (msg.displayedContent || '') + delta
          }
        },
        onEvent: (evt) => {
          // tool_call / tool_result 不展示给用户（避免浏览器控制台泄露用户输入/工具结果）
        },
        onDone: (full, err) => {
          patchAssistant(full, true, err)
        },
        onSessionId: (sid) => {
          if (!currentSessionId.value) {
            currentSessionId.value = sid
          }
        },
        onSources: (sources) => {
          attachSources(sources)
        },
      })
    } catch (e: unknown) {
      const err = e as { name?: string; message?: string }
      const msg = messages.value.find(m => m.id === aiId)
      if (err.name === 'AbortError') {
        if (msg) {
          msg.content = msg.displayedContent || '(已停止生成)'
          msg.isStreaming = false
          msg.loading = false
        }
      } else {
        if (msg) {
          // 优先展示后端透传的错误；否则网络/未知错误
          const detail = (err.message || '').trim()
          msg.content = detail ? `抱歉，${detail}` : '抱歉，发生错误，请重试。'
          msg.isStreaming = false
          msg.loading = false
        }
        console.error('Stream error', e)
      }
    } finally {
      isStreaming.value = false
      activeAiMessageId = null
      abortController = null
      void loadSessions()
    }
  }

  async function stopGenerating(): Promise<void> {
    if (currentSessionId.value) {
      try {
        await apiStopChat(currentSessionId.value)
      } catch (e) {
        console.warn('stop chat API failed', e)
      }
    }
    if (abortController) {
      abortController.abort()
    }
  }

  return {
    messages,
    currentSessionId,
    isStreaming,
    sessions,
    activeAiMessage,
    sendMessage,
    stopGenerating,
    resetSession,
    loadSessions,
    selectSession,
    deleteSession,
    clearCurrentMessages,
    pinSession,
    renameSession,
    attachSources,
  }
})
