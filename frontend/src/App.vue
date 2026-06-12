<script setup lang="ts">
import { onMounted, provide, ref, watch } from 'vue'
import { RouterView } from 'vue-router'

const isDark = ref(false)

onMounted(() => {
  const saved = localStorage.getItem('theme')
  if (saved) {
    isDark.value = saved === 'dark'
  } else {
    isDark.value = window.matchMedia('(prefers-color-scheme: dark)').matches
  }
  applyTheme()
})

watch(isDark, () => {
  applyTheme()
  localStorage.setItem('theme', isDark.value ? 'dark' : 'light')
})

function applyTheme() {
  document.documentElement.setAttribute('data-theme', isDark.value ? 'dark' : 'light')
}

function toggleTheme() {
  isDark.value = !isDark.value
}

provide('toggleTheme', toggleTheme)
provide('isDark', isDark)
</script>

<template>
  <RouterView />
</template>

<style>
/* ===== 主题色（暗紫 + 冷蓝渐变） ===== */
:root {
  --bg-primary: #f7f7fb;
  --bg-secondary: #ffffff;
  --bg-tertiary: #f1f1f7;
  --bg-overlay: rgba(255, 255, 255, 0.75);

  --text-primary: #1a1a2e;
  --text-secondary: #6b6b80;
  --text-muted: #9a9aac;

  --border-color: #e6e6f0;
  --border-strong: #d0d0e0;

  --accent-color: #6c5ce7;
  --accent-hover: #5848d6;
  --accent-soft: rgba(108, 92, 231, 0.1);
  --accent-glow: rgba(108, 92, 231, 0.35);

  --gradient-primary: linear-gradient(135deg, #6c5ce7 0%, #4834d4 100%);
  --gradient-soft: linear-gradient(135deg, rgba(108, 92, 231, 0.08), rgba(72, 52, 212, 0.02));
  --gradient-user: linear-gradient(135deg, #6c5ce7 0%, #4834d4 100%);

  --user-bubble: #6c5ce7;
  --user-text: #ffffff;
  --assistant-bubble: #ffffff;
  --assistant-text: #1a1a2e;

  --header-bg: rgba(255, 255, 255, 0.85);
  --input-bg: #ffffff;

  --shadow-sm: 0 1px 2px rgba(20, 20, 50, 0.05);
  --shadow: 0 4px 12px rgba(20, 20, 50, 0.08);
  --shadow-lg: 0 10px 30px rgba(20, 20, 50, 0.12);
  --shadow-glow: 0 8px 24px rgba(108, 92, 231, 0.25);

  --radius-sm: 8px;
  --radius: 12px;
  --radius-lg: 16px;
  --radius-xl: 20px;

  --transition: 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

[data-theme="dark"] {
  --bg-primary: #0f0f1a;
  --bg-secondary: #1a1a2e;
  --bg-tertiary: #252542;
  --bg-overlay: rgba(26, 26, 46, 0.8);

  --text-primary: #ecedf5;
  --text-secondary: #a0a0b8;
  --text-muted: #6c6c80;

  --border-color: #2d2d4a;
  --border-strong: #3d3d5c;

  --accent-color: #8b7cff;
  --accent-hover: #a39bff;
  --accent-soft: rgba(139, 124, 255, 0.18);
  --accent-glow: rgba(139, 124, 255, 0.4);

  --gradient-primary: linear-gradient(135deg, #8b7cff 0%, #5a4bd1 100%);
  --gradient-soft: linear-gradient(135deg, rgba(139, 124, 255, 0.1), rgba(90, 75, 209, 0.03));
  --gradient-user: linear-gradient(135deg, #8b7cff 0%, #5a4bd1 100%);

  --user-bubble: #6c5ce7;
  --user-text: #ffffff;
  --assistant-bubble: #252542;
  --assistant-text: #ecedf5;

  --header-bg: rgba(15, 15, 26, 0.85);
  --input-bg: #1a1a2e;

  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.3);
  --shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
  --shadow-lg: 0 10px 30px rgba(0, 0, 0, 0.5);
  --shadow-glow: 0 8px 24px rgba(139, 124, 255, 0.35);
}

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html, body {
  height: 100%;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC',
    'Hiragino Sans GB', 'Microsoft YaHei', Roboto, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  background: var(--bg-primary);
  color: var(--text-primary);
  transition: background var(--transition), color var(--transition);
}

#app {
  width: 100%;
  height: 100vh;
  overflow: hidden;
}

/* ===== 滚动条 ===== */
::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb {
  background: var(--border-strong);
  border-radius: 4px;
}
::-webkit-scrollbar-thumb:hover { background: var(--text-muted); }

/* ===== 全局动画 ===== */
@keyframes fadeInUp {
  from { opacity: 0; transform: translateY(8px); }
  to   { opacity: 1; transform: translateY(0); }
}
@keyframes fadeIn {
  from { opacity: 0; }
  to   { opacity: 1; }
}
</style>
