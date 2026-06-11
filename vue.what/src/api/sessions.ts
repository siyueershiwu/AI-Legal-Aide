import client from './client'
import type { ChatSession, SessionDetail } from '@/types/api'

export async function listSessions(): Promise<{ sessions: ChatSession[]; total: number }> {
  const { data } = await client.get<{ sessions: ChatSession[]; total: number }>('/sessions')
  return data
}

export async function getSession(id: string): Promise<SessionDetail> {
  const { data } = await client.get<SessionDetail>(`/sessions/${id}`)
  return data
}

export async function deleteSession(id: string): Promise<void> {
  await client.delete(`/sessions/${id}`)
}

export async function clearSessionMessages(id: string): Promise<void> {
  await client.delete(`/sessions/${id}/messages`)
}

export async function pinSession(id: string): Promise<void> {
  await client.post(`/sessions/${id}/pin`)
}

export async function renameSession(id: string, title: string): Promise<void> {
  await client.put(`/sessions/${id}/title`, { title })
}

export async function searchHistory(keyword: string): Promise<{ results: unknown[]; total: number }> {
  const { data } = await client.get<{ results: unknown[]; total: number }>('/history/search', {
    params: { keyword },
  })
  return data
}
