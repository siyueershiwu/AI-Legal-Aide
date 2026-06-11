import client from './client'

export interface ChatStreamPayload {
  session_id?: string | null
  message: string
  file_ids?: string[]
}

export async function stopChat(sessionId: string): Promise<void> {
  await client.post(`/chat/stop/${sessionId}`)
}
