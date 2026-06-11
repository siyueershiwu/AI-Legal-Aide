<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'

const props = defineProps<{
  title?: string
  message?: string
  placeholder?: string
  defaultValue?: string
}>()

const emit = defineEmits<{
  confirm: [value: string]
  cancel: []
}>()

const visible = ref(false)
const input = ref('')
const inputRef = ref<HTMLInputElement | null>(null)

watch(visible, async (v) => {
  if (v) {
    input.value = props.defaultValue || ''
    await nextTick()
    inputRef.value?.focus()
    inputRef.value?.select()
  }
})

function show(): void {
  visible.value = true
}
function close(): void {
  visible.value = false
  emit('cancel')
}
function onConfirm(): void {
  visible.value = false
  emit('confirm', input.value.trim())
}
function onKeydown(e: KeyboardEvent): void {
  if (e.key === 'Enter') onConfirm()
  else if (e.key === 'Escape') close()
}

defineExpose({ show, close })
</script>

<template>
  <Teleport to="body">
    <div v-if="visible" class="dialog-mask" @click.self="close">
      <div class="dialog-box" role="dialog" aria-modal="true">
        <h3 v-if="title" class="dialog-title">{{ title }}</h3>
        <p v-if="message" class="dialog-message">{{ message }}</p>
        <input
          ref="inputRef"
          v-model="input"
          :placeholder="placeholder"
          class="dialog-input"
          @keydown="onKeydown"
        />
        <div class="dialog-actions">
          <button class="btn btn-secondary" @click="close">取消</button>
          <button class="btn btn-primary" @click="onConfirm">确定</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.dialog-mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
}
.dialog-box {
  background: var(--bg-secondary);
  border-radius: 12px;
  padding: 24px;
  width: 360px;
  max-width: 90vw;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
}
.dialog-title { margin: 0 0 12px; color: var(--text-primary); }
.dialog-message { margin: 0 0 12px; color: var(--text-secondary); }
.dialog-input {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid var(--border-color);
  border-radius: 6px;
  background: var(--input-bg, white);
  color: var(--text-primary);
  font-size: 0.95rem;
  box-sizing: border-box;
}
.dialog-input:focus { outline: none; border-color: #4f46e5; }
.dialog-actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 16px; }
.btn {
  padding: 8px 16px;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.9rem;
}
.btn-primary { background: #4f46e5; color: white; }
.btn-primary:hover { background: #4338ca; }
.btn-secondary { background: var(--bg-tertiary); color: var(--text-primary); }
.btn-secondary:hover { background: var(--border-color); }
</style>
