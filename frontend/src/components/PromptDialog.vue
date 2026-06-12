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
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
  animation: fadeIn 0.2s ease;
}
.dialog-box {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: 28px;
  width: 360px;
  max-width: 90vw;
  box-shadow: var(--shadow-lg);
  animation: fadeInUp 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}
.dialog-title { margin: 0 0 12px; color: var(--text-primary); font-size: 1.05rem; font-weight: 600; }
.dialog-message { margin: 0 0 12px; color: var(--text-secondary); font-size: 0.9rem; }
.dialog-input {
  width: 100%;
  padding: 11px 14px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
  background: var(--input-bg, white);
  color: var(--text-primary);
  font-size: 0.95rem;
  box-sizing: border-box;
  font-family: inherit;
  transition: all var(--transition);
}
.dialog-input:focus {
  outline: none;
  border-color: var(--accent-color);
  box-shadow: 0 0 0 3px var(--accent-soft);
}
.dialog-actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 20px; }
.btn {
  padding: 8px 18px;
  border: none;
  border-radius: var(--radius);
  cursor: pointer;
  font-size: 0.9rem;
  font-weight: 500;
  transition: all var(--transition);
}
.btn-primary {
  background: var(--gradient-primary);
  color: white;
  box-shadow: var(--shadow-glow);
}
.btn-primary:hover { transform: translateY(-1px); box-shadow: 0 10px 28px rgba(108, 92, 231, 0.4); }
.btn-secondary { background: var(--bg-tertiary); color: var(--text-primary); }
.btn-secondary:hover { background: var(--border-color); }
</style>
