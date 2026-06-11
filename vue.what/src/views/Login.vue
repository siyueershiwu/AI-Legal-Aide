<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const username = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)
const router = useRouter()
const auth = useAuthStore()

async function handleLogin() {
  error.value = ''
  loading.value = true
  try {
    await auth.login(username.value, password.value)
    router.push({ name: 'chat' })
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    error.value = err.response?.data?.detail || '登录失败'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="auth-container">
    <div class="auth-box">
      <h2>登录</h2>
      <form @submit.prevent="handleLogin">
        <input v-model="username" type="text" placeholder="用户名" required :disabled="loading" />
        <input v-model="password" type="password" placeholder="密码" required :disabled="loading" />
        <button type="submit" :disabled="loading">{{ loading ? '登录中…' : '登录' }}</button>
        <p v-if="error" class="error">{{ error }}</p>
      </form>
      <p class="switch-auth">
        还没有账号？<router-link to="/register">注册</router-link>
      </p>
    </div>
  </div>
</template>

<style scoped>
.auth-container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
  background: var(--bg-primary);
}
.auth-box {
  padding: 40px;
  background: var(--bg-secondary);
  border-radius: 12px;
  width: 360px;
  box-shadow: var(--shadow);
}
.auth-box h2 {
  text-align: center;
  color: var(--text-primary);
  margin-bottom: 24px;
}
.auth-box input {
  width: 100%;
  padding: 12px;
  margin: 8px 0;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  background: var(--input-bg);
  color: var(--text-primary);
  font-size: 14px;
}
.auth-box input:focus {
  outline: none;
  border-color: var(--accent-color);
}
.auth-box button {
  width: 100%;
  padding: 12px;
  margin-top: 16px;
  background: var(--accent-color);
  color: white;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-size: 16px;
  transition: background 0.2s;
}
.auth-box button:hover:not(:disabled) {
  background: var(--accent-hover);
}
.auth-box button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.error {
  color: #dc2626;
  font-size: 0.875rem;
  margin-top: 12px;
  text-align: center;
}
.switch-auth {
  text-align: center;
  margin-top: 16px;
  color: var(--text-secondary);
}
.switch-auth a {
  color: var(--accent-color);
  text-decoration: none;
}
.switch-auth a:hover {
  text-decoration: underline;
}
</style>
