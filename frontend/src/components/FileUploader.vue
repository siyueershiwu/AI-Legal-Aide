<script setup lang="ts">
import { ref } from 'vue'
import { useUploadStore } from '@/stores/upload'

const emit = defineEmits<{ 'upload-complete': [files: unknown[]] }>()
const upload = useUploadStore()
const isDragOver = ref(false)
const fileInputRef = ref<HTMLInputElement | null>(null)
const uploadUploadError = ref('')

async function handleFiles(fileList: FileList | File[]) {
  const files = Array.from(fileList)
  const errors: string[] = []
  for (const f of files) {
    try {
      await upload.upload(f)
    } catch {
      errors.push(f.name)
    }
  }
  if (errors.length) {
    uploadUploadError.value = `以下文件上传失败：${errors.join('、')}`
    setTimeout(() => (uploadUploadError.value = ''), 3000)
  }
  emit('upload-complete', upload.files)
  if (fileInputRef.value) fileInputRef.value.value = ''
}

function onDragOver(e: DragEvent) {
  e.preventDefault()
  isDragOver.value = true
}
function onDragLeave(e: DragEvent) {
  e.preventDefault()
  isDragOver.value = false
}
function onDrop(e: DragEvent) {
  e.preventDefault()
  isDragOver.value = false
  if (e.dataTransfer?.files && e.dataTransfer.files.length > 0) {
    void handleFiles(e.dataTransfer.files)
  }
}
function onChange(e: Event) {
  const target = e.target as HTMLInputElement
  if (target.files) void handleFiles(target.files)
}
function trigger() {
  fileInputRef.value?.click()
}
</script>

<template>
  <div
    class="file-uploader"
    :class="{ 'drag-over': isDragOver }"
    @dragover="onDragOver"
    @dragleave="onDragLeave"
    @drop="onDrop"
  >
    <input
      ref="fileInputRef"
      type="file"
      accept="image/*,.pdf,.doc,.docx,.txt,.md,.csv"
      multiple
      @change="onChange"
      style="display:none"
    />
    <button class="upload-button" :disabled="upload.isUploading" @click="trigger" title="上传文件或图片（支持拖拽）">
      <img src="/picture/shangchuan.jpg" class="upload-icon" alt="上传" />
    </button>
    <span v-if="uploadUploadError" class="upload-error">{{ uploadUploadError }}</span>
  </div>
</template>

<style scoped>
.file-uploader { display: inline-flex; align-items: center; transition: all 0.2s; position: relative; }
.upload-error {
  position: absolute;
  top: 100%;
  left: 0;
  margin-top: 4px;
  font-size: 0.75rem;
  color: #ef4444;
  white-space: nowrap;
  background: var(--bg-secondary);
  padding: 2px 6px;
  border-radius: 4px;
}
.file-uploader.drag-over { transform: scale(1.1); }
.file-uploader.drag-over .upload-button {
  border-color: var(--accent-color);
  background: var(--accent-soft);
  box-shadow: 0 0 0 3px var(--accent-soft);
}
.upload-button {
  width: 36px;
  height: 36px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
  background: var(--bg-secondary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all var(--transition);
  overflow: hidden;
}
.upload-button:hover:not(:disabled) {
  border-color: var(--accent-color);
  background: var(--accent-soft);
  transform: translateY(-1px);
}
.upload-button:disabled { opacity: 0.5; cursor: not-allowed; }
.upload-icon { width: 100%; height: 100%; object-fit: cover; border-radius: var(--radius); }
</style>
