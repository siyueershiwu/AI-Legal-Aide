<script setup lang="ts">
import { nextTick, onMounted, onUnmounted, ref, watch, type ComponentPublicInstance } from 'vue'
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
const dropdownPos = ref<{ top: number; left: number } | null>(null)
const confirmRef = ref<InstanceType<typeof ConfirmDialog> | null>(null)
const promptRef = ref<InstanceType<typeof PromptDialog> | null>(null)

let pendingDeleteId: string | null = null
let pendingRenameSession: ChatSession | null = null

// 记录每个 "..." 按钮的 DOM 引用，按 id 索引，供 toggleMenu 算坐标
const menuButtonRefs = ref<Map<string, HTMLButtonElement>>(new Map())
function setMenuButtonRef(id: string, el: Element | ComponentPublicInstance | null) {
  if (el instanceof HTMLButtonElement) menuButtonRefs.value.set(id, el)
  else menuButtonRefs.value.delete(id)
}

onMounted(() => {
  void chat.loadSessions()
  document.addEventListener('click', closeMenu)
  window.addEventListener('scroll', closeMenu, true)  // 捕获：任何祖先滚动都关
  window.addEventListener('resize', closeMenu)
})

onUnmounted(() => {
  document.removeEventListener('click', closeMenu)
  window.removeEventListener('scroll', closeMenu, true)
  window.removeEventListener('resize', closeMenu)
})

function closeMenu() {
  activeMenuId.value = null
  dropdownPos.value = null
}

async function toggleMenu(e: Event, id: string) {
  e.stopPropagation()
  if (activeMenuId.value === id) {
    closeMenu()
    return
  }
  const btn = menuButtonRefs.value.get(id)
  if (!btn) return
  // 等下一帧再算 rect，避免 transform/transition 中坐标不准
  await nextTick()
  const rect = btn.getBoundingClientRect()
  // 右对齐：dropdown 右边缘 = 按钮右边缘；top = 按钮底部 + 4px
  dropdownPos.value = {
    top: rect.bottom + 4,
    left: rect.right - 140,
  }
  activeMenuId.value = id
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

// 兜底：activeMenuId 变了但坐标没跟上（比如响应式数据驱动），不修正就报 undefined
watch(activeMenuId, (id) => {
  if (id && !dropdownPos.value) {
    const btn = menuButtonRefs.value.get(id)
    if (btn) {
      const rect = btn.getBoundingClientRect()
      dropdownPos.value = { top: rect.bottom + 4, left: rect.right - 140 }
    }
  }
})
</script>

<template>
  <div class="chat-history" @click="closeMenu">
    <div class="new-chat-bar">
      <button class="new-chat-btn" @click="emit('new-chat')">
        <span class="new-chat-icon">+</span>
        <span>新对话</span>
      </button>
    </div>
    <div class="history-header">
      <h3>历史对话</h3>
      <button class="refresh-btn" @click="chat.loadSessions()" title="刷新">
        <img src="/picture/123.png" alt="刷新" class="refresh-icon" />
      </button>
    </div>
    <div v-if="chat.sessions.length === 0" class="empty">
      <div class="empty-icon">💬</div>
      <div>暂无历史记录</div>
    </div>
    <div v-else class="session-list">
      <div
        v-for="s in chat.sessions"
        :key="s.id"
        class="session-item"
        :class="{ active: s.id === chat.currentSessionId }"
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
        <button
          :ref="(el) => setMenuButtonRef(s.id, el)"
          class="menu-btn"
          @click="toggleMenu($event, s.id)"
          title="更多"
        >⋯</button>
      </div>
    </div>

    <!-- 三个点的菜单：用 Teleport 提到 body 层 + position: fixed，
         彻底脱离 session-list 的 overflow/stacking 上下文，
         不会再被下一条历史项 hover 状态盖住。 -->
    <Teleport to="body">
      <div
        v-if="activeMenuId && dropdownPos"
        class="dropdown-menu"
        :style="{ top: dropdownPos.top + 'px', left: dropdownPos.left + 'px' }"
        @click.stop
      >
        <button class="menu-item" @click="onPin($event, activeMenuId)">📌 置顶</button>
        <button
          class="menu-item"
          @click="onRename($event, chat.sessions.find(x => x.id === activeMenuId)!)"
        >✏️ 重命名</button>
        <button class="menu-item delete" @click="onDelete($event, activeMenuId)">🗑 删除</button>
      </div>
    </Teleport>

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
  position: relative;
}

.new-chat-bar {
  padding: 16px;
  border-bottom: 1px solid var(--border-color);
}

.new-chat-btn {
  width: 100%;
  padding: 12px 16px;
  background: var(--gradient-primary);
  border: none;
  border-radius: var(--radius);
  color: white;
  cursor: pointer;
  font-size: 0.9rem;
  font-weight: 500;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  transition: all var(--transition);
  box-shadow: var(--shadow-glow);
}

.new-chat-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 12px 32px rgba(108, 92, 231, 0.4);
}

.new-chat-btn:active { transform: translateY(0); }

.new-chat-icon {
  font-size: 1.2rem;
  font-weight: 300;
  line-height: 1;
}

.history-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px 8px;
}

.history-header h3 {
  margin: 0;
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.refresh-btn {
  background: none;
  border: none;
  cursor: pointer;
  padding: 4px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background var(--transition), transform 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}
.refresh-btn:hover { background: var(--bg-tertiary); transform: rotate(180deg); }
.refresh-btn:active { transform: rotate(360deg); }

.refresh-icon {
  width: 20px;
  height: 20px;
  object-fit: contain;
  display: block;
}

.empty {
  padding: 40px 20px;
  text-align: center;
  color: var(--text-muted);
  font-size: 0.875rem;
}
.empty-icon {
  font-size: 2rem;
  margin-bottom: 8px;
  opacity: 0.5;
}

.session-list { flex: 1; overflow-y: auto; padding: 4px 0; }

.session-item {
  position: relative;
  padding: 12px 20px;
  cursor: pointer;
  margin: 2px 8px;
  border-radius: var(--radius);
  transition: all var(--transition);
}

.session-item:hover {
  background: var(--bg-tertiary);
  transform: translateX(2px);
}

.session-item.active {
  background: var(--accent-soft);
  box-shadow: inset 3px 0 0 var(--accent-color);
}

.session-item:hover .menu-btn { opacity: 1; }

.session-title {
  display: flex;
  align-items: center;
  gap: 4px;
  font-weight: 500;
  color: var(--text-primary);
  font-size: 0.9rem;
  margin-bottom: 4px;
  padding-right: 28px;
}

.pin-icon { font-size: 0.75rem; flex-shrink: 0; }

.title-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-meta {
  display: flex;
  justify-content: space-between;
  font-size: 0.75rem;
  color: var(--text-muted);
  padding-right: 28px;
}

.menu-btn {
  position: absolute;
  top: 12px;
  right: 12px;
  background: none;
  border: none;
  cursor: pointer;
  opacity: 0;
  padding: 4px 8px;
  border-radius: 4px;
  color: var(--text-secondary);
  font-size: 1.1rem;
  transition: all var(--transition);
}
.menu-btn:hover { background: var(--border-color); }

@media (max-width: 768px) {
  .chat-history {
    position: fixed;
    left: 0;
    top: 0;
    bottom: 0;
    z-index: 95;
    transform: translateX(-100%);
    transition: transform 0.3s ease;
    box-shadow: var(--shadow-lg);
  }
  .chat-history.mobile-show { transform: translateX(0); }
}
</style>

<!--
  dropdown-menu 提到 body 层渲染（scoped 不生效，样式用 :global 等价方案）。
  Vue 3 scoped 对 Teleport 到 body 的元素依然会把 data-v-xxx 加到子节点，
  配合 :deep() 让子作用域里的规则穿透。
-->
<style>
.dropdown-menu {
  position: fixed;
  min-width: 140px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
  box-shadow: var(--shadow-lg);
  z-index: 9999;
  overflow: hidden;
  animation: fadeInUp 0.15s ease;
  /* 屏蔽宿主组件的 :hover 透传：菜单自己处理 hover */
  pointer-events: auto;
}

.dropdown-menu .menu-item {
  display: block;
  width: 100%;
  padding: 10px 14px;
  background: none;
  border: none;
  text-align: left;
  font-size: 0.85rem;
  color: var(--text-primary);
  cursor: pointer;
  transition: background var(--transition);
}
.dropdown-menu .menu-item:hover { background: var(--bg-tertiary); }
.dropdown-menu .menu-item.delete:hover { background: rgba(239, 68, 68, 0.1); color: #ef4444; }
</style>
