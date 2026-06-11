<script setup lang="ts">
import { inject, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import ChatWindow from '@/components/ChatWindow.vue'
import ChatInput from '@/components/ChatInput.vue'
import FileUploader from '@/components/FileUploader.vue'
import ChatHistory from '@/components/ChatHistory.vue'
import { useAuthStore } from '@/stores/auth'
import { useChatStore } from '@/stores/chat'
import { useUploadStore } from '@/stores/upload'

const auth = useAuthStore()
const chat = useChatStore()
const upload = useUploadStore()
const router = useRouter()

const isDark = inject<{ value: boolean }>('isDark')
const toggleTheme = inject<() => void>('toggleTheme')

const showSidebar = ref(false)

function toggleSidebar() {
  showSidebar.value = !showSidebar.value
}

function handleLogout() {
  auth.logout()
  router.push({ name: 'login' })
}

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

onMounted(() => {
  void chat.loadSessions()
})
</script>

<template>
  <div class="chat-room">
    <button class="mobile-menu-btn" @click="toggleSidebar">☰</button>
    <div v-if="showSidebar" class="sidebar-overlay" @click="toggleSidebar"></div>

    <ChatHistory
      :class="{ 'mobile-show': showSidebar }"
      @select="(id) => chat.selectSession(id)"
      @delete="(id) => chat.deleteSession(id)"
      @pin="(id) => chat.pinSession(id)"
      @rename="(id, t) => chat.renameSession(id, t)"
      @new-chat="chat.resetSession()"
    />

    <div class="chat-main">
      <div class="chat-header">
        <div class="header-left">
          <button
            class="theme-btn"
            @click="toggleTheme"
            :title="isDark?.value ? '切换到浅色模式' : '切换到深色模式'"
          >
            {{ isDark?.value ? '☀️' : '🌙' }}
          </button>
        </div>
        <h2>AI 助手</h2>
        <div class="header-actions">
          <span class="username">{{ auth.username }}</span>
          <button v-if="chat.isStreaming" class="stop-btn" @click="chat.stopGenerating()">
            ⏹️ 停止
          </button>
          <button class="clear-btn" @click="chat.clearCurrentMessages()">🗑️ 清空</button>
          <button class="logout-btn" @click="handleLogout">🚪</button>
        </div>
      </div>

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
  </div>
</template>

<style scoped>
.chat-room {
  display: flex;
  height: 100vh;
  width: 100%;
  background: var(--bg-primary);
}
.mobile-menu-btn {
  display: none;
  position: fixed;
  top: 12px;
  left: 12px;
  z-index: 100;
  width: 40px;
  height: 40px;
  border-radius: 8px;
  background: var(--bg-tertiary);
  border: none;
  font-size: 20px;
  cursor: pointer;
}
.sidebar-overlay {
  display: none;
}
.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 20px;
  background: var(--header-bg);
  border-bottom: 1px solid var(--border-color);
}
.chat-header h2 {
  margin: 0;
  font-size: 1.2rem;
  color: var(--text-primary);
}
.header-left { display: flex; align-items: center; gap: 8px; }
.theme-btn, .clear-btn, .stop-btn {
  padding: 8px 12px;
  background: var(--bg-tertiary);
  border: none;
  border-radius: 8px;
  font-size: 0.875rem;
  cursor: pointer;
  color: var(--text-primary);
}
.theme-btn:hover, .clear-btn:hover { background: var(--border-color); }
.stop-btn { background: #ef4444; color: white; }
.stop-btn:hover { background: #dc2626; }
.header-actions { display: flex; align-items: center; gap: 8px; }
.username { color: var(--text-secondary); font-size: 0.875rem; margin-right: 8px; }
.logout-btn {
  padding: 8px 12px;
  background: var(--bg-tertiary);
  border: none;
  border-radius: 8px;
  cursor: pointer;
  color: var(--text-primary);
}
.logout-btn:hover { background: #fee2e2; }
.chat-container { flex: 1; overflow-y: auto; background: var(--bg-secondary); }
.chat-footer { padding: 8px 20px 16px; background: var(--bg-primary); }
.input-area {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-width: 900px;
  margin: 0 auto;
  width: 100%;
}
.upload-tip { color: var(--text-secondary); font-size: 0.875rem; padding: 10px 4px; }
.upload-line { display: flex; align-items: center; gap: 8px; padding: 0 20px 0 34px; }
.input-line { display: flex; align-items: flex-end; gap: 8px; padding: 0 20px; }
@media (max-width: 768px) {
  .mobile-menu-btn { display: block; }
  .sidebar-overlay {
    display: block;
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,0.5);
    z-index: 90;
  }
  .chat-header { padding-left: 60px; }
  .chat-header h2 { font-size: 1rem; }
}
</style>
