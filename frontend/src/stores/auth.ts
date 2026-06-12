import { defineStore } from 'pinia'
import { computed, ref, watch } from 'vue'
import * as authApi from '@/api/auth'
import { clearToken, setToken } from '@/api/client'
import type { User } from '@/types/api'

export const useAuthStore = defineStore('auth', () => {
  // localStorage 是单一真源；store 只是 reactive 镜像
  const token = ref<string>(localStorage.getItem('token') || '')
  const user = ref<User | null>(null)
  const username = ref<string>('')

  const isAuthenticated = computed(() => !!token.value)

  // 监听 token 变化 → 写回 localStorage
  watch(token, (v) => {
    if (v) {
      setToken(v)
    } else {
      clearToken()
    }
  })

  // 跨 tab 同步：A tab 退出登录 → B tab 也跟着失效
  if (typeof window !== 'undefined') {
    window.addEventListener('storage', (e) => {
      if (e.key === 'token') {
        token.value = e.newValue || ''
        if (!token.value) user.value = null
      }
    })
  }

  async function login(usernameInput: string, password: string): Promise<void> {
    const data = await authApi.login({ username: usernameInput, password })
    token.value = data.access_token
    username.value = data.username
  }

  async function register(
    usernameInput: string,
    password: string,
    email?: string,
  ): Promise<void> {
    const data = await authApi.register({ username: usernameInput, password, email })
    token.value = data.access_token
    username.value = data.username
  }

  async function loadMe(): Promise<void> {
    if (!token.value) return
    try {
      user.value = await authApi.fetchMe()
      username.value = user.value.username
    } catch {
      logout()
    }
  }

  function logout(): void {
    token.value = ''
    user.value = null
    username.value = ''
  }

  return {
    token,
    user,
    username,
    isAuthenticated,
    login,
    register,
    loadMe,
    logout,
  }
})
