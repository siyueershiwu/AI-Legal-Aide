import client from './client'
import type { UploadedFile } from '@/types/api'

export async function uploadFile(file: File): Promise<UploadedFile> {
  const form = new FormData()
  form.append('file', file)
  const { data } = await client.post<{
    file_id: string
    url: string
    type: string
    name: string
    size: number
  }>('/files/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 60_000,
  })
  return {
    id: data.file_id,
    url: data.url,
    type: data.type,
    name: data.name,
    size: data.size,
  }
}
