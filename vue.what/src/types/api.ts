// 共享类型
export interface User {
  id: string
  username: string
  email?: string | null
  avatar?: string | null
  created_at: string
}

export interface LoginRequest {
  username: string
  password: string
}

export interface RegisterRequest {
  username: string
  password: string
  email?: string
}

export interface AuthResponse {
  success: boolean
  access_token: string
  token_type: string
  user_id: string
  username: string
}

export type Role = 'user' | 'assistant'

export interface Message {
  id: string
  role: Role
  content: string
  created_at: string
  displayedContent?: string
  isStreaming?: boolean
  loading?: boolean
  files?: Array<{ id: string; url: string; type: string; name: string }>
  image?: string | null
}

export interface ChatSession {
  id: string
  title: string | null
  pinned: boolean
  message_count: number
  created_at: string
  updated_at: string
}

export interface SessionDetail {
  id: string
  title: string | null
  pinned: boolean
  created_at: string
  updated_at: string
  messages: Message[]
}

export interface UploadedFile {
  id: string
  url: string
  type: string
  name: string
  size?: number
}

export interface SSEEvent {
  content?: string
  done?: boolean
  event?: 'tool_call' | 'tool_result'
  name?: string
  error?: string | null
}
