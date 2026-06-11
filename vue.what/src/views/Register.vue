<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const username = ref('')
const email = ref('')
const password = ref('')
const confirmPassword = ref('')
const error = ref('')
const loading = ref(false)
const router = useRouter()
const auth = useAuthStore()

async function handleRegister() {
  error.value = ''
  if (password.value !== confirmPassword.value) {
    error.value = '两次密码不一致'
    return
  }
  if (password.value.length < 6) {
    error.value = '密码至少6位'
    return
  }
  loading.value = true
  try {
    await auth.register(username.value, password.value, email.value || undefined)
    router.push({ name: 'chat' })
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    error.value = err.response?.data?.detail || '注册失败'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="auth-container">
    <div class="auth-box">
      <h2>注册</h2>
      <form @submit.prevent="handleRegister">
        <input v-model="username" type="text" placeholder="用户名（至少3位）" required :disabled="loading" />
        <input v-model="email" type="email" placeholder="邮箱（可选）" :disabled="loading" />
        <input v-model="password" type="password" placeholder="密码（至少6位）" required :disabled="loading" />
        <input v-model="confirmPassword" type="password" placeholder="确认密码" required :disabled="loading" />
        <button type="submit" :disabled="loading">{{ loading ? '注册中…' : '注册' }}</button>
        <p v-if="error" class="error">{{ error }}</p>
      </form>
      <p class="switch-auth">
        已有账号？<router-link to="/login">登录</router-link>
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
