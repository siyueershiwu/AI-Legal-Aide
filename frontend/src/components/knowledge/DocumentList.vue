<script setup lang="ts">
import { computed, nextTick, onUnmounted, ref, type ComponentPublicInstance } from 'vue'
import { useKnowledgeStore } from '@/stores/knowledge'
import {
  DOC_TYPE_LABELS,
  LAW_CODE_LABELS,
  type DocTypeEnum,
  type KnowledgeDocument,
  type KnowledgeSource,
  type LawCodeEnum,
} from '@/types/api'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import PromptDialog from '@/components/PromptDialog.vue'

const emit = defineEmits<{
  'preview-search': [doc: KnowledgeDocument]
  rebuild: []
}>()

const kb = useKnowledgeStore()

// ===== 选择 =====
const selectedIds = ref<Set<string>>(new Set())
const allSelected = computed(() => {
  if (kb.documents.length === 0) return false
  return kb.documents.every((d) => selectedIds.value.has(d.id))
})

function toggleOne(id: string) {
  if (selectedIds.value.has(id)) selectedIds.value.delete(id)
  else selectedIds.value.add(id)
  selectedIds.value = new Set(selectedIds.value)
}

function toggleAll() {
  if (allSelected.value) {
    selectedIds.value = new Set()
  } else {
    selectedIds.value = new Set(kb.documents.map((d) => d.id))
  }
}

function clearSelection() {
  selectedIds.value = new Set()
}

// ===== 单条操作 =====
const activeMenuId = ref<string | null>(null)
const dropdownPos = ref<{ top: number; left: number } | null>(null)
const menuButtonRefs = ref<Map<string, HTMLButtonElement>>(new Map())
function setMenuButtonRef(id: string, el: Element | ComponentPublicInstance | null) {
  if (el instanceof HTMLButtonElement) menuButtonRefs.value.set(id, el)
  else menuButtonRefs.value.delete(id)
}

async function toggleMenu(e: Event, id: string) {
  e.stopPropagation()
  if (activeMenuId.value === id) {
    closeMenu()
    return
  }
  const btn = menuButtonRefs.value.get(id)
  if (!btn) return
  await nextTick()
  const rect = btn.getBoundingClientRect()
  dropdownPos.value = { top: rect.bottom + 4, left: rect.right - 140 }
  activeMenuId.value = id
}

function closeMenu() {
  activeMenuId.value = null
  dropdownPos.value = null
}

// ===== 删除 =====
const confirmRef = ref<InstanceType<typeof ConfirmDialog> | null>(null)
const promptRef = ref<InstanceType<typeof PromptDialog> | null>(null)
let pendingDeleteId: string | null = null
let pendingDeleteIds: string[] | null = null
let pendingRebuild = false

function onDeleteOne(e: Event, id: string) {
  e.stopPropagation()
  closeMenu()
  pendingDeleteId = id
  confirmRef.value?.show()
}

function onBatchDelete() {
  if (selectedIds.value.size === 0) return
  pendingDeleteIds = Array.from(selectedIds.value)
  confirmRef.value?.show()
}

function onRebuild() {
  pendingRebuild = true
  promptRef.value?.show()
}

async function onConfirmDelete() {
  if (pendingDeleteId) {
    try {
      await kb.deleteDocument(pendingDeleteId)
    } catch (e) {
      console.error('delete failed', e)
    }
    pendingDeleteId = null
    clearSelection()
  } else if (pendingDeleteIds) {
    try {
      await kb.batchDelete(pendingDeleteIds)
    } catch (e) {
      console.error('batch delete failed', e)
    }
    pendingDeleteIds = null
    clearSelection()
  }
}

function onPromptConfirm(value: string) {
  if (pendingRebuild && value === 'REBUILD') {
    pendingRebuild = false
    void kb.rebuild()
  } else {
    pendingRebuild = false
  }
}

// ===== 预览检索 =====
function onPreview(e: Event, doc: KnowledgeDocument) {
  e.stopPropagation()
  closeMenu()
  emit('preview-search', doc)
}

// ===== 生命周期 =====
onUnmounted(() => {
  document.removeEventListener('click', closeMenu)
  window.removeEventListener('scroll', closeMenu, true)
  window.removeEventListener('resize', closeMenu)
})

if (typeof document !== 'undefined') {
  document.addEventListener('click', closeMenu)
  window.addEventListener('scroll', closeMenu, true)
  window.addEventListener('resize', closeMenu)
}

// ===== 工具 =====
function fmt(d: string): string {
  return new Date(d).toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function lawLabel(code: string): string {
  return LAW_CODE_LABELS[code as LawCodeEnum] ?? code
}

function docTypeLabel(t: string): string {
  return DOC_TYPE_LABELS[t as DocTypeEnum] ?? t
}

defineExpose({ clearSelection })

// preview-search 显示的 sources 状态由父组件管理；这里只 emit 事件
const _ = null as unknown as KnowledgeSource
</script>

<template>
  <div class="document-list">
    <div class="list-toolbar">
      <div class="toolbar-left">
        <button
          class="toolbar-btn danger"
          :disabled="selectedIds.size === 0 || kb.loading"
          @click="onBatchDelete"
        >
          <span>🗑</span>
          <span>批量删除</span>
          <span v-if="selectedIds.size > 0" class="badge">{{ selectedIds.size }}</span>
        </button>
        <span v-if="selectedIds.size > 0" class="selected-hint">
          已选 {{ selectedIds.size }} 项
          <button class="link-btn" @click="clearSelection">清空</button>
        </span>
      </div>
      <div class="toolbar-right">
        <button
          class="toolbar-btn warn"
          :disabled="kb.rebuilding || kb.documents.length === 0"
          @click="onRebuild"
        >
          <span>⚠</span>
          <span>{{ kb.rebuilding ? '重建中…' : '清空重建' }}</span>
        </button>
      </div>
    </div>

    <div v-if="kb.loading && kb.documents.length === 0" class="empty">
      <div class="empty-icon">⏳</div>
      <div>加载中…</div>
    </div>

    <div v-else-if="kb.documents.length === 0" class="empty">
      <div class="empty-icon">📚</div>
      <div>知识库还是空的</div>
      <div class="empty-hint">点右上「入库文档」开始收录第一份法律</div>
    </div>

    <div v-else class="table-wrapper">
      <table class="doc-table">
        <thead>
          <tr>
            <th class="col-check">
              <input
                type="checkbox"
                :checked="allSelected"
                @change="toggleAll"
                aria-label="全选"
              />
            </th>
            <th class="col-title">标题</th>
            <th class="col-law">法律</th>
            <th class="col-doctype">类型</th>
            <th class="col-ver">版本</th>
            <th class="col-status">状态</th>
            <th class="col-num">切片数</th>
            <th class="col-num">字符数</th>
            <th class="col-time">入库时间</th>
            <th class="col-act">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="doc in kb.documents"
            :key="doc.id"
            :class="{ selected: selectedIds.has(doc.id) }"
            @click="toggleOne(doc.id)"
          >
            <td class="col-check" @click.stop>
              <input
                type="checkbox"
                :checked="selectedIds.has(doc.id)"
                @change="toggleOne(doc.id)"
                :aria-label="`选择 ${doc.title}`"
              />
            </td>
            <td class="col-title" :title="doc.title">{{ doc.title }}</td>
            <td class="col-law">{{ lawLabel(doc.law_code) }}</td>
            <td class="col-doctype">{{ docTypeLabel(doc.doc_type) }}</td>
            <td class="col-ver">{{ doc.version || '—' }}</td>
            <td class="col-status">
              <span v-if="doc.is_current" class="status-tag current">现行</span>
              <span v-else class="status-tag repealed">已废止</span>
            </td>
            <td class="col-num">{{ doc.chunk_count }}</td>
            <td class="col-num">{{ doc.char_count }}</td>
            <td class="col-time">{{ fmt(doc.created_at) }}</td>
            <td class="col-act" @click.stop>
              <button
                :ref="(el) => setMenuButtonRef(doc.id, el as Element | null)"
                class="menu-btn"
                @click="(e) => toggleMenu(e, doc.id)"
                :aria-label="`操作 ${doc.title}`"
              >
                ⋯
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <Teleport to="body">
      <div
        v-if="activeMenuId"
        class="dropdown"
        :style="{ top: dropdownPos?.top + 'px', left: dropdownPos?.left + 'px' }"
        @click.stop
      >
        <button
          class="dropdown-item"
          @click="(e) => {
            const d = kb.documents.find((x) => x.id === activeMenuId)
            if (d) onPreview(e, d)
          }"
        >
          <span>👁</span><span>预览检索</span>
        </button>
        <button
          class="dropdown-item danger"
          @click="(e) => {
            const id = activeMenuId
            closeMenu()
            if (id) onDeleteOne(e, id)
          }"
        >
          <span>🗑</span><span>删除</span>
        </button>
      </div>
    </Teleport>

    <ConfirmDialog
      ref="confirmRef"
      :title="pendingDeleteIds ? `批量删除 ${pendingDeleteIds.length} 项？` : '确认删除？'"
      :message="pendingDeleteIds ? '删除后无法恢复，相关向量也会被清理。' : '该文档的向量数据也会一并删除。'"
      confirm-text="删除"
      cancel-text="取消"
      variant="danger"
      @confirm="onConfirmDelete"
    />
    <PromptDialog
      ref="promptRef"
      title="确认清空重建"
      message="该操作会先清空 ChromaDB，再重新跑所有文档的入库。输入 REBUILD 确认。"
      placeholder="REBUILD"
      @confirm="onPromptConfirm"
    />
  </div>
</template>

<style scoped>
.document-list { display: flex; flex-direction: column; flex: 1; min-height: 0; }

.list-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
  margin-bottom: 12px;
  flex-wrap: wrap;
  gap: 8px;
}

.toolbar-left, .toolbar-right { display: flex; align-items: center; gap: 10px; }

.toolbar-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 14px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
  background: var(--bg-tertiary);
  color: var(--text-primary);
  font-size: 0.85rem;
  cursor: pointer;
  transition: all var(--transition);
}
.toolbar-btn:hover:not(:disabled) {
  background: var(--accent-soft);
  border-color: var(--accent-color);
  color: var(--accent-color);
}
.toolbar-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.toolbar-btn.danger { color: #ef4444; border-color: rgba(239, 68, 68, 0.3); }
.toolbar-btn.danger:hover:not(:disabled) {
  background: rgba(239, 68, 68, 0.1);
  border-color: #ef4444;
  color: #ef4444;
}
.toolbar-btn.warn {
  color: #f59e0b;
  border-color: rgba(245, 158, 11, 0.3);
}
.toolbar-btn.warn:hover:not(:disabled) {
  background: rgba(245, 158, 11, 0.1);
  border-color: #f59e0b;
  color: #f59e0b;
}
.badge {
  background: #ef4444;
  color: white;
  font-size: 0.7rem;
  padding: 1px 6px;
  border-radius: 10px;
  margin-left: 4px;
  min-width: 18px;
  text-align: center;
}

.selected-hint {
  color: var(--text-secondary);
  font-size: 0.85rem;
}
.link-btn {
  background: none;
  border: none;
  color: var(--accent-color);
  cursor: pointer;
  text-decoration: underline;
  font-size: 0.85rem;
  margin-left: 6px;
  padding: 0;
}

.empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 24px;
  color: var(--text-secondary);
  background: var(--bg-secondary);
  border: 1px dashed var(--border-color);
  border-radius: var(--radius-lg);
}
.empty-icon { font-size: 3rem; margin-bottom: 12px; opacity: 0.6; }
.empty-hint { font-size: 0.85rem; margin-top: 4px; color: var(--text-muted); }

.table-wrapper {
  flex: 1;
  min-height: 0;
  overflow: auto;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
}

.doc-table { width: 100%; border-collapse: collapse; font-size: 0.88rem; }
.doc-table thead { background: var(--bg-tertiary); position: sticky; top: 0; z-index: 1; }
.doc-table th {
  text-align: left;
  padding: 11px 12px;
  font-weight: 600;
  color: var(--text-secondary);
  border-bottom: 1px solid var(--border-color);
  font-size: 0.82rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  white-space: nowrap;
}
.doc-table td {
  padding: 12px;
  border-bottom: 1px solid var(--border-color);
  color: var(--text-primary);
}
.doc-table tbody tr { cursor: pointer; transition: background var(--transition); }
.doc-table tbody tr:hover { background: var(--accent-soft); }
.doc-table tbody tr.selected { background: var(--accent-soft); }

.col-check { width: 36px; }
.col-title { max-width: 280px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.col-law, .col-doctype, .col-ver { white-space: nowrap; }
.col-num { text-align: right; font-variant-numeric: tabular-nums; }
.col-time { white-space: nowrap; font-size: 0.82rem; color: var(--text-secondary); }
.col-act { width: 50px; text-align: right; }

.status-tag {
  display: inline-block;
  font-size: 0.7rem;
  padding: 1px 6px;
  border-radius: 8px;
  font-weight: 500;
}
.status-tag.current {
  background: rgba(34, 197, 94, 0.15);
  color: #16a34a;
}
.status-tag.repealed {
  background: rgba(239, 68, 68, 0.15);
  color: #ef4444;
}

.menu-btn {
  width: 28px;
  height: 28px;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 6px;
  cursor: pointer;
  color: var(--text-primary);
  font-size: 1.1rem;
  line-height: 1;
}
.menu-btn:hover { background: var(--bg-tertiary); border-color: var(--border-color); }

.dropdown {
  position: fixed;
  z-index: 200;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
  box-shadow: var(--shadow-lg);
  min-width: 140px;
  padding: 4px;
  animation: fadeIn 0.12s ease;
}
.dropdown-item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 8px 12px;
  background: transparent;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  color: var(--text-primary);
  font-size: 0.85rem;
  text-align: left;
  transition: background var(--transition);
}
.dropdown-item:hover { background: var(--accent-soft); color: var(--accent-color); }
.dropdown-item.danger:hover { background: rgba(239, 68, 68, 0.1); color: #ef4444; }
</style>
