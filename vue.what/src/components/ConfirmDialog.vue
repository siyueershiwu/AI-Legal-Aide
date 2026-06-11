<script setup lang="ts">
import { ref } from 'vue'

const props = defineProps<{
  title?: string
  message: string
  confirmText?: string
  cancelText?: string
  variant?: 'default' | 'danger'
}>()

const emit = defineEmits<{
  confirm: []
  cancel: []
}>()

const visible = ref(false)

function show(): void {
  visible.value = true
}
function close(): void {
  visible.value = false
  emit('cancel')
}
function onConfirm(): void {
  visible.value = false
  emit('confirm')
}

defineExpose({ show, close })
</script>

<template>
  <Teleport to="body">
    <div v-if="visible" class="dialog-mask" @click.self="close">
      <div class="dialog-box" role="dialog" aria-modal="true">
        <h3 v-if="title" class="dialog-title">{{ title }}</h3>
        <p class="dialog-message">{{ message }}</p>
        <div class="dialog-actions">
          <button class="btn btn-secondary" @click="close">
            {{ cancelText || '取消' }}
          </button>
          <button
            class="btn"
            :class="props.variant === 'danger' ? 'btn-danger' : 'btn-primary'"
            @click="onConfirm"
          >
            {{ confirmText || '确定' }}
          </button>
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
.dialog-message { margin: 0 0 20px; color: var(--text-secondary); line-height: 1.5; }
.dialog-actions { display: flex; gap: 8px; justify-content: flex-end; }
.btn {
  padding: 8px 16px;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.9rem;
}
.btn-primary { background: #4f46e5; color: white; }
.btn-primary:hover { background: #4338ca; }
.btn-danger { background: #dc2626; color: white; }
.btn-danger:hover { background: #b91c1c; }
.btn-secondary { background: var(--bg-tertiary); color: var(--text-primary); }
.btn-secondary:hover { background: var(--border-color); }
</style>
