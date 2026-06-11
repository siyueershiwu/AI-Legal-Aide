import { defineStore } from 'pinia'
import { ref } from 'vue'
import { uploadFile as apiUploadFile } from '@/api/files'
import type { UploadedFile } from '@/types/api'

export const useUploadStore = defineStore('upload', () => {
  const isUploading = ref(false)
  const files = ref<UploadedFile[]>([])

  async function upload(file: File): Promise<void> {
    isUploading.value = true
    try {
      const uploaded = await apiUploadFile(file)
      files.value.push(uploaded)
    } catch (e) {
      console.error('Upload failed', e)
      throw e
    } finally {
      isUploading.value = false
    }
  }

  function clear(): void {
    files.value = []
  }

  function remove(id: string): void {
    files.value = files.value.filter((f) => f.id !== id)
  }

  return { isUploading, files, upload, clear, remove }
})
