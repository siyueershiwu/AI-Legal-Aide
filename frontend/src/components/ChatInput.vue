<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'

const props = defineProps<{ hasAttachments?: boolean }>()
const emit = defineEmits<{
  send: [text: string]
  'paste-image': [file: File]
}>()

const inputText = ref('')
const textareaRef = ref<HTMLTextAreaElement | null>(null)

function autoResize() {
  const ta = textareaRef.value
  if (!ta) return
  ta.style.height = 'auto'
  ta.style.height = Math.min(ta.scrollHeight, 150) + 'px'
}

watch(inputText, () => {
  void nextTick(autoResize)
})

function handleSend() {
  if (!inputText.value.trim() && !props.hasAttachments) return
  emit('send', inputText.value)
  inputText.value = ''
  void nextTick(() => {
    if (textareaRef.value) textareaRef.value.style.height = 'auto'
  })
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSend()
  }
}

function handlePaste(e: ClipboardEvent) {
  const items = e.clipboardData?.items
  if (!items) return
  for (const item of Array.from(items)) {
    if (item.type.startsWith('image/')) {
      e.preventDefault()
      const file = item.getAsFile()
      if (file) emit('paste-image', file)
      return
    }
  }
}
</script>

<template>
  <div class="chat-input">
    <textarea
      ref="textareaRef"
      v-model="inputText"
      @keydown="handleKeydown"
      @paste="handlePaste"
      placeholder="输入消息... (Enter 发送，Shift+Enter 换行，支持直接粘贴图片)"
      rows="1"
      class="input-textarea"
    ></textarea>
    <button
      class="send-button"
      :disabled="!inputText.trim() && !hasAttachments"
      @click="handleSend"
      title="发送消息"
    >
      <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
        <path d="M5 12h14M13 5l7 7-7 7" />
      </svg>
    </button>
  </div>
</template>

<style scoped>
.chat-input {
  display: flex;
  align-items: flex-end;
  gap: 10px;
  flex: 1;
  background: var(--bg-secondary);
  padding: 6px;
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-color);
  transition: all var(--transition);
  box-shadow: var(--shadow-sm);
}

.chat-input:focus-within {
  border-color: var(--accent-color);
  box-shadow: 0 0 0 3px var(--accent-soft), var(--shadow);
}

.input-textarea {
  flex: 1;
  padding: 10px 14px;
  border: none;
  background: transparent;
  resize: none;
  overflow: hidden;
  font-family: inherit;
  font-size: 0.95rem;
  line-height: 1.5;
  min-height: 24px;
  max-height: 150px;
  outline: none;
  color: var(--text-primary);
  width: 100%;
  box-sizing: border-box;
}

.input-textarea::placeholder {
  color: var(--text-muted);
}

.send-button {
  width: 40px;
  height: 40px;
  background: var(--gradient-primary);
  color: white;
  border: none;
  border-radius: var(--radius);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: all var(--transition);
  box-shadow: var(--shadow-glow);
}

.send-button svg { transition: transform var(--transition); }

.send-button:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 10px 28px rgba(108, 92, 231, 0.4);
}
.send-button:hover:not(:disabled) svg { transform: translateX(2px); }

.send-button:active:not(:disabled) { transform: translateY(0); }

.send-button:disabled {
  background: var(--bg-tertiary);
  color: var(--text-muted);
  cursor: not-allowed;
  box-shadow: none;
}
</style>
