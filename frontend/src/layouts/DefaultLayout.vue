<script setup lang="ts">
import { computed, inject, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import ChatHistory from '@/components/ChatHistory.vue'
import { useAuthStore } from '@/stores/auth'
import { useChatStore } from '@/stores/chat'

const auth = useAuthStore()
const chat = useChatStore()
const router = useRouter()
const route = useRoute()

const isDark = inject<{ value: boolean }>('isDark')
const toggleTheme = inject<() => void>('toggleTheme')

// 移动端 sidebar 抽屉
const drawerOpen = ref(false)
function toggleDrawer() {
  drawerOpen.value = !drawerOpen.value
}
function closeDrawer() {
  drawerOpen.value = false
}

interface NavItem {
  name: string
  label: string
  icon: string
  to: string
}

const navItems: NavItem[] = [
  { name: 'chat', label: '对话', icon: '💬', to: '/' },
  { name: 'knowledge', label: '知识库', icon: '📚', to: '/knowledge' },
]

// 当前路由名 → 用于高亮
const activeName = computed(() => (route.name as string) || 'chat')

// 当前是否在 chat 页面（决定是否在侧边栏下方展示 ChatHistory 会话列表）
const showChatHistory = computed(() => activeName.value === 'chat')

function isActive(name: string): boolean {
  return activeName.value === name
}

function navigate(to: string) {
  if (route.path !== to) {
    void router.push(to)
  }
  closeDrawer()
}

function handleLogout() {
  auth.logout()
  void router.push({ name: 'login' })
}
</script>

<template>
  <div class="default-layout">
    <button
      class="mobile-menu-btn"
      @click="toggleDrawer"
      :aria-label="drawerOpen ? '关闭菜单' : '打开菜单'"
    >
      <span v-if="!drawerOpen">☰</span>
      <span v-else>✕</span>
    </button>

    <Teleport to="body">
      <div
        v-if="drawerOpen"
        class="sidebar-overlay"
        @click="closeDrawer"
        role="presentation"
      ></div>
    </Teleport>

    <aside class="sidebar" :class="{ 'mobile-show': drawerOpen }">
      <div class="brand">
        <div class="brand-mark">法</div>
        <div class="brand-text">AI 法律助手</div>
      </div>

      <nav class="nav">
        <button
          v-for="item in navItems"
          :key="item.name"
          class="nav-item"
          :class="{ active: isActive(item.name) }"
          @click="navigate(item.to)"
        >
          <span class="nav-icon">{{ item.icon }}</span>
          <span class="nav-label">{{ item.label }}</span>
        </button>
      </nav>

      <div v-if="showChatHistory" class="history-slot">
        <ChatHistory
          @select="(id) => chat.selectSession(id)"
          @delete="(id) => chat.deleteSession(id)"
          @pin="(id) => chat.pinSession(id)"
          @rename="(id, t) => chat.renameSession(id, t)"
          @new-chat="chat.resetSession()"
        />
      </div>
    </aside>

    <div class="main">
      <header class="topbar">
        <div class="topbar-left">
          <h2 class="page-title">
            {{ navItems.find((n) => n.name === activeName)?.label || '' }}
          </h2>
        </div>
        <div class="topbar-right">
          <button
            class="icon-btn"
            @click="toggleTheme"
            :title="isDark?.value ? '切换到浅色模式' : '切换到深色模式'"
            :aria-label="isDark?.value ? '切换到浅色模式' : '切换到深色模式'"
          >
            {{ isDark?.value ? '☀️' : '🌙' }}
          </button>
          <span class="username" :title="auth.username">{{ auth.username }}</span>
          <button
            class="icon-btn logout-btn"
            @click="handleLogout"
            title="退出登录"
            aria-label="退出登录"
          >
            ⏻
          </button>
        </div>
      </header>

      <main class="content">
        <router-view />
      </main>
    </div>
  </div>
</template>

<style scoped>
.default-layout {
  display: flex;
  height: 100vh;
  width: 100%;
  background: var(--bg-primary);
  background-image: var(--gradient-soft);
  overflow: hidden;
}

.mobile-menu-btn {
  display: none;
  position: fixed;
  top: 14px;
  left: 14px;
  z-index: 100;
  width: 40px;
  height: 40px;
  border-radius: var(--radius);
  background: var(--bg-overlay);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  border: 1px solid var(--border-color);
  font-size: 18px;
  cursor: pointer;
  box-shadow: var(--shadow);
  color: var(--text-primary);
}

.sidebar-overlay {
  display: none;
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 90;
}

.sidebar {
  width: 260px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: var(--bg-secondary);
  border-right: 1px solid var(--border-color);
  height: 100%;
  overflow: hidden;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 18px 20px;
  border-bottom: 1px solid var(--border-color);
  flex-shrink: 0;
}

.brand-mark {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius);
  background: var(--gradient-primary);
  color: white;
  font-weight: 700;
  font-size: 1.1rem;
  box-shadow: var(--shadow-glow);
  flex-shrink: 0;
}

.brand-text {
  font-weight: 600;
  font-size: 1.05rem;
  letter-spacing: 0.05em;
  background: var(--gradient-primary);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  color: transparent;
}

.nav {
  display: flex;
  flex-direction: column;
  padding: 12px;
  gap: 4px;
  flex-shrink: 0;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: var(--radius);
  background: transparent;
  border: 1px solid transparent;
  color: var(--text-primary);
  font-size: 0.95rem;
  font-weight: 500;
  cursor: pointer;
  transition: all var(--transition);
  text-align: left;
  width: 100%;
}

.nav-item:hover {
  background: var(--accent-soft);
}

.nav-item.active {
  background: var(--accent-soft);
  border-color: var(--accent-color);
  color: var(--accent-color);
}

.nav-icon {
  font-size: 1.1rem;
  width: 20px;
  text-align: center;
}

.nav-label {
  flex: 1;
}

.history-slot {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  border-top: 1px solid var(--border-color);
  overflow: hidden;
}

.history-slot :deep(.chat-history) {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  border: none;
}

.history-slot :deep(.history-list) {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
}

.main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 24px;
  background: var(--header-bg);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--border-color);
  position: relative;
  z-index: 10;
  flex-shrink: 0;
}

.topbar::after {
  content: '';
  position: absolute;
  bottom: -1px;
  left: 50%;
  transform: translateX(-50%);
  width: 60%;
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--accent-color), transparent);
  opacity: 0.5;
}

.page-title {
  margin: 0;
  font-size: 1.1rem;
  font-weight: 600;
  color: var(--text-primary);
  letter-spacing: 0.05em;
}

.topbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  background: var(--bg-tertiary);
  border: 1px solid transparent;
  border-radius: var(--radius);
  font-size: 1.1rem;
  cursor: pointer;
  color: var(--text-primary);
  transition: all var(--transition);
}

.icon-btn:hover {
  background: var(--accent-soft);
  border-color: var(--accent-color);
  color: var(--accent-color);
}

.logout-btn:hover {
  background: rgba(239, 68, 68, 0.1) !important;
  color: #ef4444 !important;
  border-color: rgba(239, 68, 68, 0.3) !important;
}

.username {
  color: var(--text-secondary);
  font-size: 0.875rem;
  padding: 6px 12px;
  background: var(--accent-soft);
  border-radius: var(--radius);
  max-width: 160px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.content {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

@media (max-width: 768px) {
  .mobile-menu-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
  }
  .sidebar-overlay {
    display: block;
  }
  .sidebar {
    position: fixed;
    top: 0;
    left: 0;
    bottom: 0;
    z-index: 95;
    transform: translateX(-100%);
    transition: transform 0.25s ease;
    box-shadow: var(--shadow-lg);
  }
  .sidebar.mobile-show {
    transform: translateX(0);
  }
  .topbar {
    padding-left: 64px;
    padding-right: 12px;
  }
  .page-title {
    font-size: 0.95rem;
  }
  .username {
    display: none;
  }
}
</style>
