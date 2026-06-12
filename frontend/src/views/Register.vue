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
    <div class="bg-blob blob-1"></div>
    <div class="bg-blob blob-2"></div>
    <div class="auth-box">
      <div class="brand">
        <div class="brand-icon">⚔️</div>
        <h1 class="brand-name">AI 法律助手</h1>
        <p class="brand-tag">创建账号 · 开始对话</p>
      </div>
      <form @submit.prevent="handleRegister" class="auth-form">
        <div class="form-group">
          <input v-model="username" type="text" placeholder="用户名（至少3位）" required :disabled="loading" />
        </div>
        <div class="form-group">
          <input v-model="email" type="email" placeholder="邮箱（可选）" :disabled="loading" />
        </div>
        <div class="form-group">
          <input v-model="password" type="password" placeholder="密码（至少6位）" required :disabled="loading" />
        </div>
        <div class="form-group">
          <input v-model="confirmPassword" type="password" placeholder="确认密码" required :disabled="loading" />
        </div>
        <button type="submit" :disabled="loading" class="submit-btn">
          <span v-if="!loading">注 册</span>
          <span v-else>注册中…</span>
        </button>
        <p v-if="error" class="error">{{ error }}</p>
      </form>
      <p class="switch-auth">
        已有账号？<router-link to="/login">直接登录</router-link>
      </p>
    </div>
  </div>
</template>

<style scoped>
.auth-container {
  position: relative;
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
  background: var(--bg-primary);
  overflow: hidden;
}

.bg-blob {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  opacity: 0.5;
  pointer-events: none;
  z-index: 0;
}
.blob-1 {
  width: 500px;
  height: 500px;
  background: #c084fc;
  top: -200px;
  right: -150px;
  animation: float 14s ease-in-out infinite;
}
.blob-2 {
  width: 400px;
  height: 400px;
  background: var(--accent-color);
  bottom: -150px;
  left: -100px;
  animation: float 16s ease-in-out infinite reverse;
}

@keyframes float {
  0%, 100% { transform: translate(0, 0) scale(1); }
  50% { transform: translate(40px, -40px) scale(1.1); }
}

.auth-box {
  position: relative;
  z-index: 1;
  padding: 36px;
  background: var(--bg-overlay);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-xl);
  width: 400px;
  max-width: calc(100vw - 32px);
  box-shadow: var(--shadow-lg);
  animation: fadeInUp 0.5s ease;
}

.brand {
  text-align: center;
  margin-bottom: 28px;
}
.brand-icon {
  font-size: 2.5rem;
  margin-bottom: 8px;
  filter: drop-shadow(0 4px 12px var(--accent-glow));
}
.brand-name {
  font-size: 1.5rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  background: var(--gradient-primary);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  color: transparent;
  margin-bottom: 4px;
}
.brand-tag {
  font-size: 0.8rem;
  color: var(--text-muted);
  letter-spacing: 0.05em;
}

.auth-form { display: flex; flex-direction: column; gap: 12px; }

.form-group { position: relative; }

.auth-box input {
  width: 100%;
  padding: 12px 16px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
  background: var(--bg-secondary);
  color: var(--text-primary);
  font-size: 0.95rem;
  transition: all var(--transition);
  font-family: inherit;
}
.auth-box input::placeholder { color: var(--text-muted); }
.auth-box input:focus {
  outline: none;
  border-color: var(--accent-color);
  box-shadow: 0 0 0 3px var(--accent-soft);
}
.auth-box input:disabled { opacity: 0.5; cursor: not-allowed; }

.submit-btn {
  width: 100%;
  padding: 13px;
  margin-top: 4px;
  background: var(--gradient-primary);
  color: white;
  border: none;
  border-radius: var(--radius);
  cursor: pointer;
  font-size: 0.95rem;
  font-weight: 500;
  letter-spacing: 0.1em;
  transition: all var(--transition);
  box-shadow: var(--shadow-glow);
  font-family: inherit;
}
.submit-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 12px 32px rgba(108, 92, 231, 0.45);
}
.submit-btn:active:not(:disabled) { transform: translateY(0); }
.submit-btn:disabled { opacity: 0.7; cursor: not-allowed; }

.error {
  color: #ef4444;
  font-size: 0.85rem;
  text-align: center;
  padding: 8px;
  background: rgba(239, 68, 68, 0.08);
  border-radius: var(--radius-sm);
  border: 1px solid rgba(239, 68, 68, 0.2);
}

.switch-auth {
  text-align: center;
  margin-top: 20px;
  color: var(--text-secondary);
  font-size: 0.9rem;
}
.switch-auth a {
  color: var(--accent-color);
  text-decoration: none;
  font-weight: 500;
}
.switch-auth a:hover { text-decoration: underline; }
</style>
