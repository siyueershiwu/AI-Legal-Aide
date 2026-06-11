import client from './client'
import type { AuthResponse, LoginRequest, RegisterRequest, User } from '@/types/api'

export async function login(payload: LoginRequest): Promise<AuthResponse> {
  const { data } = await client.post<AuthResponse>('/auth/login', payload)
  return data
}

export async function register(payload: RegisterRequest): Promise<AuthResponse> {
  const { data } = await client.post<AuthResponse>('/auth/register', payload)
  return data
}

export async function fetchMe(): Promise<User> {
  const { data } = await client.get<User>('/auth/me')
  return data
}
