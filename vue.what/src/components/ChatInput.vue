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
    >↑</button>
  </div>
</template>

<style scoped>
.chat-input {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  flex: 1;
  background: white;
}
.input-textarea {
  flex: 1;
  padding: 10px 14px;
  border: 1px solid #d1d5db;
  border-radius: 20px;
  resize: none;
  overflow: hidden;
  font-family: inherit;
  font-size: 0.95rem;
  line-height: 1.5;
  min-height: 42px;
  max-height: 150px;
  outline: none;
  transition: border-color 0.2s, box-shadow 0.2s;
  width: 100%;
  box-sizing: border-box;
}
.input-textarea:focus {
  border-color: #4f46e5;
  box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.1);
}
.send-button {
  width: 36px;
  height: 36px;
  background: #4f46e5;
  color: white;
  border: none;
  border-radius: 50%;
  font-size: 1.2rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.send-button:hover:not(:disabled) { background: #4338ca; }
.send-button:active:not(:disabled) { transform: scale(0.95); }
.send-button:disabled { background: #d1d5db; cursor: not-allowed; }
</style>
