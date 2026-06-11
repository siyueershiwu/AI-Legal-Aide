<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { useChatStore } from '@/stores/chat'
import type { ChatSession } from '@/types/api'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import PromptDialog from '@/components/PromptDialog.vue'

const emit = defineEmits<{
  select: [id: string]
  delete: [id: string]
  pin: [id: string]
  rename: [id: string, title: string]
  'new-chat': []
}>()

const chat = useChatStore()
const activeMenuId = ref<string | null>(null)
const confirmRef = ref<InstanceType<typeof ConfirmDialog> | null>(null)
const promptRef = ref<InstanceType<typeof PromptDialog> | null>(null)

let pendingDeleteId: string | null = null
let pendingRenameSession: ChatSession | null = null

onMounted(() => {
  void chat.loadSessions()
  document.addEventListener('click', closeMenu)
})

onUnmounted(() => {
  document.removeEventListener('click', closeMenu)
})

function closeMenu() {
  activeMenuId.value = null
}

function toggleMenu(e: Event, id: string) {
  e.stopPropagation()
  activeMenuId.value = activeMenuId.value === id ? null : id
}

function onPin(e: Event, id: string) {
  e.stopPropagation()
  closeMenu()
  emit('pin', id)
}

function onRename(e: Event, s: ChatSession) {
  e.stopPropagation()
  closeMenu()
  pendingRenameSession = s
  promptRef.value?.show()
}

function onPromptConfirm(value: string) {
  if (pendingRenameSession && value) {
    emit('rename', pendingRenameSession.id, value)
  }
  pendingRenameSession = null
}

function onDelete(e: Event, id: string) {
  e.stopPropagation()
  closeMenu()
  pendingDeleteId = id
  confirmRef.value?.show()
}

function onConfirmDelete() {
  if (pendingDeleteId) emit('delete', pendingDeleteId)
  pendingDeleteId = null
}

function fmt(d: string): string {
  return new Date(d).toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}
</script>

<template>
  <div class="chat-history" @click="closeMenu">
    <div class="new-chat-bar">
      <button class="new-chat-btn" @click="emit('new-chat')">➕ 新对话</button>
    </div>
    <div class="history-header">
      <h3>历史对话</h3>
      <button class="refresh-btn" @click="chat.loadSessions()" title="刷新">🔄</button>
    </div>
    <div v-if="chat.sessions.length === 0" class="empty">暂无历史记录</div>
    <div v-else class="session-list">
      <div
        v-for="s in chat.sessions"
        :key="s.id"
        class="session-item"
        @click="emit('select', s.id)"
      >
        <div class="session-title">
          <span v-if="s.pinned" class="pin-icon">📌</span>
          <span class="title-text">{{ s.title || '新对话' }}</span>
        </div>
        <div class="session-meta">
          <span>{{ fmt(s.updated_at) }}</span>
          <span>{{ s.message_count }} 条</span>
        </div>
        <button class="menu-btn" @click="toggleMenu($event, s.id)" title="更多">…</button>
        <div v-if="activeMenuId === s.id" class="dropdown-menu" @click.stop>
          <button class="menu-item" @click="onPin($event, s.id)">📌 置顶</button>
          <button class="menu-item" @click="onRename($event, s)">✏️ 重命名</button>
          <button class="menu-item delete" @click="onDelete($event, s.id)">🗑️ 删除</button>
        </div>
      </div>
    </div>

    <ConfirmDialog
      ref="confirmRef"
      title="删除对话"
      message="确定要删除这条对话吗？删除后无法恢复。"
      confirm-text="删除"
      variant="danger"
      @confirm="onConfirmDelete"
    />
    <PromptDialog
      ref="promptRef"
      title="重命名对话"
      placeholder="请输入新标题"
      :default-value="pendingRenameSession?.title || ''"
      @confirm="onPromptConfirm"
    />
  </div>
</template>

<style scoped>
.chat-history {
  width: 280px;
  min-width: 280px;
  background: var(--bg-secondary);
  border-right: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  height: 100vh;
}
.new-chat-bar { padding: 12px 16px; border-bottom: 1px solid var(--border-color); }
.new-chat-btn {
  width: 100%;
  padding: 10px 16px;
  background: var(--accent-color);
  border: none;
  border-radius: 8px;
  color: white;
  cursor: pointer;
  font-size: 0.9rem;
}
.new-chat-btn:hover { background: var(--accent-hover); }
.history-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 20px;
  border-bottom: 1px solid var(--border-color);
}
.history-header h3 { margin: 0; font-size: 1rem; color: var(--text-secondary); }
.refresh-btn {
  background: none;
  border: none;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 4px;
}
.refresh-btn:hover { background: var(--bg-tertiary); }
.empty { padding: 20px; text-align: center; color: var(--text-secondary); }
.session-list { flex: 1; overflow-y: auto; }
.session-item {
  position: relative;
  padding: 14px 20px;
  cursor: pointer;
  border-bottom: 1px solid var(--border-color);
}
.session-item:hover { background: var(--bg-tertiary); }
.session-item:hover .menu-btn { opacity: 1; }
.session-title {
  display: flex;
  align-items: center;
  gap: 4px;
  font-weight: 500;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 180px;
  margin-bottom: 4px;
}
.pin-icon { font-size: 0.8rem; flex-shrink: 0; }
.title-text { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 150px; }
.session-meta {
  display: flex;
  justify-content: space-between;
  font-size: 0.8rem;
  color: var(--text-secondary);
}
.menu-btn {
  position: absolute;
  top: 50%;
  right: 12px;
  transform: translateY(-50%);
  background: none;
  border: none;
  cursor: pointer;
  opacity: 0;
  padding: 4px 8px;
  border-radius: 4px;
}
.menu-btn:hover { background: var(--border-color); }
.dropdown-menu {
  position: absolute;
  top: 40px;
  right: 12px;
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  box-shadow: var(--shadow);
  z-index: 100;
  min-width: 120px;
  overflow: hidden;
}
.menu-item {
  display: block;
  width: 100%;
  padding: 10px 14px;
  background: none;
  border: none;
  text-align: left;
  font-size: 0.875rem;
  color: var(--text-primary);
  cursor: pointer;
}
.menu-item:hover { background: var(--bg-tertiary); }
.menu-item.delete:hover { background: #fee2e2; color: #dc2626; }

@media (max-width: 768px) {
  .chat-history {
    position: fixed;
    left: 0;
    top: 0;
    bottom: 0;
    z-index: 95;
    transform: translateX(-100%);
    transition: transform 0.3s ease;
  }
  .chat-history.mobile-show { transform: translateX(0); }
}
</style>
