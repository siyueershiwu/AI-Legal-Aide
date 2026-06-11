<script setup lang="ts">
import { computed } from 'vue'
import { useMarkdown } from '@/composables/useMarkdown'
import type { Message } from '@/types/api'

const props = defineProps<{ messages: Message[] }>()

const { render } = useMarkdown()

function getHtml(msg: Message): string {
  const text = msg.isStreaming && msg.displayedContent !== undefined
    ? msg.displayedContent
    : msg.content
  if (msg.loading && !text) return '思考中...'
  return render(text || '')
}

function copy(content: string) {
  void navigator.clipboard.writeText(content)
}

const lastMessage = computed(() => props.messages[props.messages.length - 1] ?? null)
</script>

<template>
  <div class="chat-window">
    <div v-if="messages.length === 0" class="empty-state">发送消息开始对话</div>
    <div
      v-for="msg in messages"
      :key="msg.id"
      class="message"
      :class="{ user: msg.role === 'user', assistant: msg.role === 'assistant' }"
    >
      <div class="avatar">
        <img v-if="msg.role === 'assistant'" src="/picture/touxiang.jpg" class="avatar-img" alt="AI" />
        <span v-else>👤</span>
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
          <div class="message-text" v-html="getHtml(msg)"></div>
          <span v-if="msg.loading || msg.isStreaming" class="loading-cursor">|</span>
        </div>
        <div v-if="msg.role === 'assistant' && !msg.isStreaming" class="message-actions">
          <button class="action-btn" @click="copy(msg.content)" title="复制">📋</button>
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
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.message { display: flex; gap: 12px; animation: fadeIn 0.3s ease; }
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
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
.message.user .content { background: #4f46e5; color: white; }
.message.assistant .content { background: #f3f4f6; color: #1f2937; }
.avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  flex-shrink: 0;
  overflow: hidden;
}
.avatar-img { width: 100%; height: 100%; object-fit: cover; }
.message.user .avatar { background: #e0e7ff; }
.message.assistant .avatar { background: #fef3c7; }
.content {
  max-width: 100%;
  padding: 12px 16px;
  border-radius: 16px;
  line-height: 1.6;
  word-break: break-word;
}
.message-text { word-break: break-word; }
.message-text :deep(h1) { font-size: 1.4em; margin: 0.5em 0; }
.message-text :deep(h2) { font-size: 1.2em; margin: 0.5em 0; }
.message-text :deep(h3) { font-size: 1.1em; margin: 0.5em 0; }
.message-text :deep(blockquote) {
  border-left: 3px solid #d1d5db;
  padding-left: 12px;
  margin: 8px 0;
  color: #6b7280;
}
.message-text :deep(.inline-code) {
  background: rgba(0,0,0,0.08);
  padding: 2px 6px;
  border-radius: 4px;
  font-family: monospace;
  font-size: 0.9em;
}
.message-text :deep(pre) {
  background: #1e1e1e;
  color: #d4d4d4;
  border-radius: 8px;
  padding: 12px;
  margin: 8px 0;
  overflow-x: auto;
}
.message-text :deep(pre code) { font-family: 'Consolas', 'Monaco', monospace; font-size: 0.9em; }
.message-text :deep(table) { border-collapse: collapse; margin: 8px 0; font-size: 0.9em; }
.message-text :deep(th), .message-text :deep(td) {
  border: 1px solid #d1d5db;
  padding: 6px 12px;
  text-align: left;
}
.message-text :deep(th) { background: #f3f4f6; }
.message-text :deep(ul), .message-text :deep(ol) { margin: 8px 0; padding-left: 24px; }
.message-text :deep(a) { color: #4f46e5; text-decoration: underline; }
.chat-image {
  max-width: 300px;
  max-height: 300px;
  border-radius: 8px;
  margin-bottom: 8px;
}
.file-list { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 8px; }
.file-item {
  display: flex;
  align-items: center;
  gap: 4px;
  background: rgba(255,255,255,0.2);
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 0.875rem;
}
.loading-cursor { animation: blink 1s infinite; font-weight: bold; }
@keyframes blink {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
}
.empty-state {
  text-align: center;
  color: #9ca3af;
  padding: 40px;
  font-size: 1.1rem;
}
.message-actions { display: flex; gap: 4px; opacity: 0; transition: opacity 0.2s; }
.message:hover .message-actions { opacity: 1; }
.action-btn {
  background: transparent;
  border: none;
  cursor: pointer;
  font-size: 14px;
  padding: 4px 8px;
  border-radius: 4px;
}
.action-btn:hover { background: rgba(0,0,0,0.1); }
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
</style>
