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
:root {
  --bg-primary: #ffffff;
  --bg-secondary: #f9fafb;
  --bg-tertiary: #f3f4f6;
  --text-primary: #1f2937;
  --text-secondary: #6b7280;
  --border-color: #e5e7eb;
  --accent-color: #4f46e5;
  --accent-hover: #4338ca;
  --user-bubble: #4f46e5;
  --user-text: #ffffff;
  --assistant-bubble: #f3f4f6;
  --assistant-text: #1f2937;
  --shadow: 0 1px 3px rgba(0,0,0,0.1);
  --header-bg: #ffffff;
  --input-bg: #ffffff;
}

[data-theme="dark"] {
  --bg-primary: #1a1a1a;
  --bg-secondary: #2d2d2d;
  --bg-tertiary: #3d3d3d;
  --text-primary: #f3f4f6;
  --text-secondary: #9ca3af;
  --border-color: #404040;
  --accent-color: #6366f1;
  --accent-hover: #818cf8;
  --user-bubble: #6366f1;
  --user-text: #ffffff;
  --assistant-bubble: #3d3d3d;
  --assistant-text: #f3f4f6;
  --shadow: 0 1px 3px rgba(0,0,0,0.3);
  --header-bg: #2d2d2d;
  --input-bg: #3d3d3d;
}

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  -webkit-font-smoothing: antialiased;
  background: var(--bg-primary);
  color: var(--text-primary);
}

#app {
  width: 100%;
  height: 100vh;
}
</style>
