<script setup lang="ts">
import ChatWindow from '@/components/ChatWindow.vue'
import ChatInput from '@/components/ChatInput.vue'
import FileUploader from '@/components/FileUploader.vue'
import { useChatStore } from '@/stores/chat'
import { useUploadStore } from '@/stores/upload'

const chat = useChatStore()
const upload = useUploadStore()

async function handleSend(text: string) {
  const fileIds = upload.files.map((f) => f.id)
  const files = upload.files.map((f) => ({
    id: f.id,
    url: f.url,
    type: f.type,
    name: f.name,
  }))
  await chat.sendMessage(text, fileIds, files)
  upload.clear()
}

function handlePasteImage(file: File) {
  void upload.upload(file)
}
</script>

<template>
  <div class="chat-room">
    <div class="chat-container">
      <ChatWindow :messages="chat.messages" />
    </div>

    <div class="chat-footer">
      <div class="input-area">
        <ChatInput
          @send="handleSend"
          :has-attachments="upload.files.length > 0"
          @paste-image="handlePasteImage"
        />
        <div class="upload-line">
          <FileUploader @upload-complete="() => {}" />
          <span v-if="upload.isUploading" class="upload-tip">正在上传…</span>
          <span v-else-if="upload.files.length > 0" class="upload-tip">
            已上传 {{ upload.files.length }} 个文件
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.chat-room {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

.chat-container {
  flex: 1;
  overflow-y: auto;
  background: var(--bg-primary);
  min-height: 0;
}

.chat-footer {
  padding: 12px 24px 20px;
  background: var(--bg-primary);
  border-top: 1px solid var(--border-color);
  flex-shrink: 0;
}

.input-area {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-width: 900px;
  margin: 0 auto;
  width: 100%;
}

.upload-tip {
  color: var(--text-secondary);
  font-size: 0.8rem;
  padding: 4px 4px;
}

.upload-line {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 4px 0 12px;
}
</style>
