<script setup lang="ts">
import { computed, ref } from 'vue'
import { useMarkdown } from '@/composables/useMarkdown'
import {
  DOC_TYPE_LABELS,
  LAW_CODE_LABELS,
  type DocTypeEnum,
  type KnowledgeSource,
  type LawCodeEnum,
  type Message,
} from '@/types/api'

const props = defineProps<{ messages: Message[] }>()

const { render } = useMarkdown()

function getHtml(msg: Message): string {
  const text = msg.isStreaming && msg.displayedContent !== undefined
    ? msg.displayedContent
    : msg.content
  if (msg.loading && !text) return ''
  return render(text || '')
}

function copy(content: string) {
  void navigator.clipboard.writeText(content)
}

const lastMessage = computed(() => props.messages[props.messages.length - 1] ?? null)

// 引用来源：每条消息一个独立的展开状态
const expandedSources = ref<Set<string>>(new Set())
const expandedSnippets = ref<Set<string>>(new Set())  // 切某条 source 的全文/摘要

function toggleSources(msgId: string): void {
  if (expandedSources.value.has(msgId)) {
    expandedSources.value.delete(msgId)
  } else {
    expandedSources.value.add(msgId)
  }
  expandedSources.value = new Set(expandedSources.value)
}

function toggleSnippet(key: string): void {
  if (expandedSnippets.value.has(key)) {
    expandedSnippets.value.delete(key)
  } else {
    expandedSnippets.value.add(key)
  }
  expandedSnippets.value = new Set(expandedSnippets.value)
}

function lawLabel(code: string): string {
  return LAW_CODE_LABELS[code as LawCodeEnum] ?? code
}

function docTypeLabel(t: string): string {
  return DOC_TYPE_LABELS[t as DocTypeEnum] ?? t
}

function sourceKey(msgId: string, idx: number): string {
  return `${msgId}::${idx}`
}

function snippetText(s: KnowledgeSource, expanded: boolean): string {
  if (expanded) return s.snippet
  return s.snippet.length > 80 ? s.snippet.slice(0, 80) + '…' : s.snippet
}
</script>

<template>
  <div class="chat-window">
    <div v-if="messages.length === 0" class="empty-state">
      <div class="empty-icon">📜</div>
      <div class="empty-title">向 AI 律师助手问点法律问题</div>
      <div class="empty-sub">支持文字、图片、PDF、Word、Markdown · 仅基于收录法律条文回答</div>
    </div>
    <div
      v-for="msg in messages"
      :key="msg.id"
      class="message"
      :class="{ user: msg.role === 'user', assistant: msg.role === 'assistant' }"
    >
      <div class="avatar">
        <span v-if="msg.role === 'assistant'" class="ai-avatar" title="AI 律师助手">AI</span>
        <span v-else class="user-avatar">{{ (msg.role === 'user' ? 'U' : 'A') }}</span>
      </div>
      <div class="content-wrapper">
        <div class="content">
          <img v-if="msg.image" :src="msg.image" class="chat-image" :alt="msg.image" />
          <div v-if="msg.files && msg.files.length > 0" class="file-list">
            <div v-for="f in msg.files" :key="f.id" class="file-item">
              <span class="file-icon">📎</span>
              <span class="file-name">{{ f.name }}</span>
            </div>
          </div>
          <div v-if="msg.loading && !getHtml(msg)" class="thinking">
            <span class="thinking-dot"></span>
            <span class="thinking-dot"></span>
            <span class="thinking-dot"></span>
          </div>
          <div v-else class="message-text" v-html="getHtml(msg)"></div>
          <span v-if="(msg.loading || msg.isStreaming) && getHtml(msg)" class="loading-cursor">▍</span>
        </div>
        <div v-if="msg.role === 'assistant' && !msg.isStreaming && msg.content" class="message-actions">
          <button class="action-btn" @click="copy(msg.content)" title="复制">📋 复制</button>
        </div>
        <div
          v-if="msg.role === 'assistant' && msg.sources && msg.sources.length > 0"
          class="sources-block"
        >
          <button
            class="sources-toggle"
            @click="toggleSources(msg.id)"
            :aria-expanded="expandedSources.has(msg.id)"
          >
            <span class="sources-icon">📚</span>
            <span class="sources-label">引用法条 / 资料</span>
            <span class="sources-count">{{ msg.sources.length }}</span>
            <span class="sources-arrow" :class="{ open: expandedSources.has(msg.id) }">▸</span>
          </button>
          <div v-if="expandedSources.has(msg.id)" class="sources-list">
            <div
              v-for="(src, idx) in msg.sources"
              :key="idx"
              class="source-row"
            >
              <div class="source-row-head">
                <span class="source-row-num">[{{ idx + 1 }}]</span>
                <span class="source-row-title">{{ src.title }}</span>
                <span class="source-row-meta">
                  {{ lawLabel(src.law_code) }} / {{ docTypeLabel(src.doc_type) }} / {{ src.version || '—' }}
                  <span v-if="src.is_current" class="status-tag current">现行</span>
                  <span v-else class="status-tag repealed">已废止</span>
                  <span v-if="src.article_no" class="article-tag">第{{ src.article_no }}条</span>
                </span>
                <span class="source-row-score">相似度 {{ src.score }}</span>
              </div>
              <div
                class="source-row-snippet"
                @click="toggleSnippet(sourceKey(msg.id, idx))"
                :title="expandedSnippets.has(sourceKey(msg.id, idx)) ? '点击收起' : '点击展开全文'"
              >
                {{ snippetText(src, expandedSnippets.has(sourceKey(msg.id, idx))) }}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
    <div v-if="lastMessage && lastMessage.role === 'assistant' && lastMessage.isStreaming" class="sr-only">正在生成</div>
  </div>
</template>

<style scoped>
.chat-window {
  flex: 1;
  overflow-y: auto;
  padding: 24px 20px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  max-width: 900px;
  width: 100%;
  margin: 0 auto;
}

.message {
  display: flex;
  gap: 12px;
  animation: fadeInUp 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.message.user { flex-direction: row-reverse; }
.message.user .content-wrapper { align-items: flex-end; }
.message.assistant .content-wrapper { align-items: flex-start; }

.content-wrapper {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-width: 80%;
}

.avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  flex-shrink: 0;
  overflow: hidden;
  background: var(--bg-tertiary);
  box-shadow: var(--shadow-sm);
}

.ai-avatar {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--gradient-ai, var(--gradient-user));
  color: white;
  font-weight: 600;
  font-size: 0.75rem;
  letter-spacing: 0.5px;
}

.user-avatar {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--gradient-user);
  color: white;
  font-weight: 600;
  font-size: 0.95rem;
}

.content {
  max-width: 100%;
  padding: 12px 16px;
  border-radius: var(--radius-lg);
  line-height: 1.65;
  word-break: break-word;
  position: relative;
  box-shadow: var(--shadow-sm);
}

.message.user .content {
  background: var(--gradient-user);
  color: var(--user-text);
  border-bottom-right-radius: 4px;
}
.message.assistant .content {
  background: var(--assistant-bubble);
  color: var(--assistant-text);
  border: 1px solid var(--border-color);
  border-bottom-left-radius: 4px;
}

.message-text { word-break: break-word; }
.message-text :deep(p) { margin: 0.5em 0; }
.message-text :deep(p:first-child) { margin-top: 0; }
.message-text :deep(p:last-child) { margin-bottom: 0; }
.message-text :deep(h1) { font-size: 1.4em; margin: 0.7em 0 0.4em; }
.message-text :deep(h2) { font-size: 1.2em; margin: 0.6em 0 0.4em; }
.message-text :deep(h3) { font-size: 1.05em; margin: 0.6em 0 0.3em; }

.message-text :deep(blockquote) {
  border-left: 3px solid var(--accent-color);
  padding-left: 12px;
  margin: 8px 0;
  color: var(--text-secondary);
}

.message.user .message-text :deep(.inline-code),
.message.user .message-text :deep(code) {
  background: rgba(255, 255, 255, 0.18);
  color: white;
}
.message.assistant .message-text :deep(.inline-code) {
  background: var(--accent-soft);
  color: var(--accent-color);
}

.message-text :deep(.inline-code),
.message-text :deep(code) {
  padding: 2px 6px;
  border-radius: 4px;
  font-family: 'Fira Code', 'Consolas', 'Monaco', monospace;
  font-size: 0.88em;
}

.message.user .message-text :deep(pre) {
  background: rgba(0, 0, 0, 0.3);
  color: #e8e8e8;
}
.message.assistant .message-text :deep(pre) {
  background: #1e1e2e;
  color: #d4d4dc;
}

.message-text :deep(pre) {
  border-radius: var(--radius);
  padding: 14px 16px;
  margin: 10px 0;
  overflow-x: auto;
  font-size: 0.88em;
  line-height: 1.5;
}
.message-text :deep(pre code) { font-family: 'Fira Code', 'Consolas', 'Monaco', monospace; }

.message-text :deep(table) {
  border-collapse: collapse;
  margin: 10px 0;
  font-size: 0.88em;
  width: 100%;
}
.message-text :deep(th),
.message-text :deep(td) {
  border: 1px solid var(--border-color);
  padding: 8px 12px;
  text-align: left;
}
.message-text :deep(th) { background: var(--bg-tertiary); font-weight: 600; }
.message-text :deep(ul),
.message-text :deep(ol) { margin: 8px 0; padding-left: 24px; }
.message-text :deep(li) { margin: 4px 0; }

.message.user .message-text :deep(a) {
  color: #c7d2fe;
  text-decoration: underline;
}
.message.assistant .message-text :deep(a) {
  color: var(--accent-color);
  text-decoration: underline;
}

.chat-image {
  max-width: 280px;
  max-height: 280px;
  border-radius: var(--radius);
  margin-bottom: 8px;
  display: block;
  box-shadow: var(--shadow);
}

.file-list { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 8px; }

.file-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: rgba(255, 255, 255, 0.18);
  padding: 4px 10px;
  border-radius: 12px;
  font-size: 0.8rem;
  border: 1px solid rgba(255, 255, 255, 0.15);
}
.message.assistant .file-item {
  background: var(--accent-soft);
  color: var(--accent-color);
  border-color: var(--accent-color);
}
.file-icon { font-size: 0.9em; }
.file-name { max-width: 160px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.loading-cursor {
  animation: blink 1s infinite;
  font-weight: bold;
  display: inline-block;
  margin-left: 2px;
  color: var(--accent-color);
}

.thinking {
  display: flex;
  gap: 4px;
  align-items: center;
  padding: 4px 0;
}
.thinking-dot {
  width: 6px;
  height: 6px;
  background: var(--accent-color);
  border-radius: 50%;
  animation: bounce 1.2s infinite ease-in-out;
}
.thinking-dot:nth-child(2) { animation-delay: 0.15s; }
.thinking-dot:nth-child(3) { animation-delay: 0.3s; }

@keyframes bounce {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.5; }
  40% { transform: scale(1); opacity: 1; }
}

@keyframes blink {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
}

.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  padding: 60px 20px;
  text-align: center;
}
.empty-icon { font-size: 4rem; margin-bottom: 16px; opacity: 0.4; }
.empty-title { font-size: 1.1rem; color: var(--text-secondary); margin-bottom: 4px; font-weight: 500; }
.empty-sub { font-size: 0.85rem; color: var(--text-muted); }

.message-actions { display: flex; gap: 4px; opacity: 0; transition: opacity var(--transition); }
.message:hover .message-actions { opacity: 1; }

/* ===== RAG 引用来源 ===== */
.sources-block {
  margin-top: 6px;
  max-width: 100%;
}

.sources-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  background: var(--accent-soft);
  border: 1px solid var(--accent-color);
  border-radius: 12px;
  color: var(--accent-color);
  font-size: 0.78rem;
  font-weight: 500;
  cursor: pointer;
  transition: all var(--transition);
}
.sources-toggle:hover {
  background: var(--accent-color);
  color: white;
}

.sources-icon { font-size: 0.9em; }
.sources-count {
  background: var(--accent-color);
  color: white;
  padding: 0 6px;
  border-radius: 8px;
  font-size: 0.7rem;
  min-width: 18px;
  text-align: center;
}
.sources-toggle:hover .sources-count {
  background: white;
  color: var(--accent-color);
}
.sources-arrow {
  font-size: 0.7em;
  transition: transform var(--transition);
  display: inline-block;
}
.sources-arrow.open { transform: rotate(90deg); }

.sources-list {
  margin-top: 6px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  animation: fadeInUp 0.2s ease;
}

.source-row {
  background: var(--bg-tertiary);
  border-left: 3px solid var(--accent-color);
  border-radius: var(--radius);
  padding: 8px 12px;
  font-size: 0.82rem;
}

.source-row-head {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 4px;
}
.source-row-num {
  font-weight: 700;
  color: var(--accent-color);
}
.source-row-title {
  font-weight: 600;
  color: var(--text-primary);
}
.source-row-meta {
  color: var(--text-secondary);
  font-size: 0.75rem;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
}
.source-row-score {
  margin-left: auto;
  color: var(--accent-color);
  background: var(--accent-soft);
  padding: 1px 8px;
  border-radius: 10px;
  font-size: 0.72rem;
  font-variant-numeric: tabular-nums;
}

.status-tag, .article-tag {
  display: inline-block;
  font-size: 0.68rem;
  padding: 1px 6px;
  border-radius: 8px;
  font-weight: 500;
}
.status-tag.current {
  background: rgba(34, 197, 94, 0.15);
  color: #16a34a;
}
.status-tag.repealed {
  background: rgba(239, 68, 68, 0.15);
  color: #ef4444;
}
.article-tag {
  background: var(--accent-soft);
  color: var(--accent-color);
}

.source-row-snippet {
  color: var(--text-secondary);
  line-height: 1.55;
  white-space: pre-wrap;
  cursor: pointer;
  transition: color var(--transition);
}
.source-row-snippet:hover { color: var(--text-primary); }

.action-btn {
  background: transparent;
  border: 1px solid transparent;
  cursor: pointer;
  font-size: 0.8rem;
  padding: 4px 10px;
  border-radius: 6px;
  color: var(--text-secondary);
  transition: all var(--transition);
}
.action-btn:hover {
  background: var(--bg-tertiary);
  border-color: var(--border-color);
  color: var(--text-primary);
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

@media (max-width: 768px) {
  .chat-window { padding: 16px 12px; gap: 16px; }
  .content-wrapper { max-width: 85%; }
  .avatar { width: 36px; height: 36px; }
  .chat-image { max-width: 200px; max-height: 200px; }
}
</style>
