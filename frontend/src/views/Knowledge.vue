<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useKnowledgeStore } from '@/stores/knowledge'
import {
  DOC_TYPE_LABELS,
  LAW_CODE_LABELS,
  type DocTypeEnum,
  type KnowledgeDocument,
  type KnowledgeSource,
  type LawCodeEnum,
} from '@/types/api'
import StatsOverview from '@/components/knowledge/StatsOverview.vue'
import DocumentUploader from '@/components/knowledge/DocumentUploader.vue'
import DocumentList from '@/components/knowledge/DocumentList.vue'

const kb = useKnowledgeStore()

const showUploader = ref(false)
const previewDoc = ref<KnowledgeDocument | null>(null)
const previewSources = ref<KnowledgeSource[]>([])
const previewLoading = ref(false)
const previewError = ref('')

const LAW_OPTIONS: { value: '' | LawCodeEnum; label: string }[] = [
  { value: '', label: '全部' },
  ...Object.entries(LAW_CODE_LABELS).map(([v, l]) => ({ value: v as LawCodeEnum, label: l })),
]
const DOC_TYPE_OPTIONS: { value: '' | DocTypeEnum; label: string }[] = [
  { value: '', label: '全部' },
  ...Object.entries(DOC_TYPE_LABELS).map(([v, l]) => ({ value: v as DocTypeEnum, label: l })),
]
const STATUS_OPTIONS: { value: 'all' | 'current' | 'repealed'; label: string }[] = [
  { value: 'all', label: '全部' },
  { value: 'current', label: '仅现行' },
  { value: 'repealed', label: '仅已废止' },
]

function onFilterChange() {
  void kb.loadDocuments()
}

async function onPreviewSearch(doc: KnowledgeDocument) {
  previewDoc.value = doc
  previewSources.value = []
  previewError.value = ''
  previewLoading.value = true
  try {
    const r = await kb.previewSearch(
      doc.title,
      doc.law_code,
      doc.doc_type,
      5,
      !doc.is_current, // 若是废止文档预览，把 include_repealed 打开
    )
    previewSources.value = r.sources
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : '检索失败'
    previewError.value = msg
  } finally {
    previewLoading.value = false
  }
}

function closePreview() {
  previewDoc.value = null
  previewSources.value = []
  previewError.value = ''
}

onMounted(async () => {
  await Promise.all([kb.loadDocuments(), kb.loadStats(), kb.loadMeta()])
})
</script>

<template>
  <div class="knowledge-page">
    <div class="page-header">
      <div class="header-text">
        <h1>法律知识库管理</h1>
        <p class="subtitle">
          收录国内公开法律文本及配套释义、解读、对比资料。检索有限、生成为辅、严格防幻觉。
        </p>
      </div>
      <button
        class="primary-btn"
        :disabled="kb.uploading"
        @click="showUploader = true"
      >
        <span>📤</span>
        <span>入库文档</span>
      </button>
    </div>

    <StatsOverview />

    <div v-if="kb.error" class="global-error">
      <span>⚠</span>
      <span>{{ kb.error }}</span>
      <button class="link-btn" @click="kb.clearError()">关闭</button>
    </div>

    <div class="filters">
      <div class="filter-group">
        <label>法律</label>
        <select
          v-model="kb.filterLawCode"
          class="filter-select"
          @change="onFilterChange"
        >
          <option v-for="opt in LAW_OPTIONS" :key="opt.value" :value="opt.value">
            {{ opt.label }}
          </option>
        </select>
      </div>
      <div class="filter-group">
        <label>资料类型</label>
        <select
          v-model="kb.filterDocType"
          class="filter-select"
          @change="onFilterChange"
        >
          <option v-for="opt in DOC_TYPE_OPTIONS" :key="opt.value" :value="opt.value">
            {{ opt.label }}
          </option>
        </select>
      </div>
      <div class="filter-group">
        <label>状态</label>
        <select
          v-model="kb.filterStatus"
          class="filter-select"
          @change="onFilterChange"
        >
          <option v-for="opt in STATUS_OPTIONS" :key="opt.value" :value="opt.value">
            {{ opt.label }}
          </option>
        </select>
      </div>
      <button class="refresh-btn" :disabled="kb.loading" @click="kb.loadDocuments()">
        <span v-if="kb.loading">⏳</span>
        <span v-else>🔄</span>
        <span>刷新</span>
      </button>
    </div>

    <div class="list-area">
      <DocumentList
        @preview-search="onPreviewSearch"
        @rebuild="() => {} /* 子组件内已直接调 kb.rebuild() */"
      />
    </div>

    <DocumentUploader
      v-if="showUploader"
      @uploaded="showUploader = false"
      @cancel="showUploader = false"
    />

    <Teleport to="body">
      <div
        v-if="previewDoc"
        class="preview-mask"
        @click.self="closePreview"
      >
        <div class="preview-box">
          <div class="preview-header">
            <h3>👁 检索预览</h3>
            <button class="close-btn" @click="closePreview" aria-label="关闭">✕</button>
          </div>
          <p class="preview-doc-meta">
            <strong>{{ previewDoc.title }}</strong>
            · {{ LAW_CODE_LABELS[previewDoc.law_code] ?? previewDoc.law_code }}
            / {{ DOC_TYPE_LABELS[previewDoc.doc_type] ?? previewDoc.doc_type }}
            / {{ previewDoc.version || '—' }}
            <span v-if="previewDoc.is_current" class="status-tag current">现行</span>
            <span v-else class="status-tag repealed">已废止</span>
          </p>
          <p class="preview-doc-hint">
            用文档标题做 query，调一次向量检索，看入库后的命中情况。
          </p>

          <div v-if="previewLoading" class="preview-loading">⏳ 检索中…</div>
          <div v-else-if="previewError" class="preview-error">{{ previewError }}</div>
          <div v-else-if="previewSources.length === 0" class="preview-empty">
            <div class="empty-icon">🔍</div>
            <div>未找到相似片段</div>
            <div class="empty-hint">可能 chunk 切分过细 / 标题不足以召回</div>
          </div>
          <div v-else class="preview-sources">
            <div
              v-for="(src, i) in previewSources"
              :key="i"
              class="source-item"
            >
              <div class="source-header">
                <span class="source-num">[{{ i + 1 }}]</span>
                <span class="source-title">{{ src.title }}</span>
                <span class="source-meta">
                  {{ LAW_CODE_LABELS[src.law_code as LawCodeEnum] ?? src.law_code }}
                  / {{ DOC_TYPE_LABELS[src.doc_type as DocTypeEnum] ?? src.doc_type }}
                  / {{ src.version || '—' }}
                  <span v-if="src.is_current" class="status-tag current">现行</span>
                  <span v-else class="status-tag repealed">已废止</span>
                </span>
                <span class="source-score">相似度 {{ src.score }}</span>
              </div>
              <div class="source-snippet">{{ src.snippet }}</div>
            </div>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.knowledge-page {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  padding: 20px 24px;
  overflow: auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  margin-bottom: 18px;
  flex-wrap: wrap;
  gap: 12px;
}

.header-text h1 {
  margin: 0;
  font-size: 1.4rem;
  font-weight: 600;
  background: var(--gradient-primary);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  color: transparent;
}

.subtitle {
  margin: 4px 0 0;
  color: var(--text-secondary);
  font-size: 0.85rem;
}

.primary-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 9px 18px;
  background: var(--gradient-primary);
  color: white;
  border: none;
  border-radius: var(--radius);
  font-size: 0.9rem;
  font-weight: 500;
  cursor: pointer;
  box-shadow: var(--shadow-glow);
  transition: all var(--transition);
}
.primary-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 10px 28px rgba(108, 92, 231, 0.4);
}
.primary-btn:disabled { opacity: 0.6; cursor: not-allowed; }

.global-error {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: var(--radius);
  color: #ef4444;
  font-size: 0.9rem;
  margin-bottom: 14px;
}
.link-btn {
  margin-left: auto;
  background: none;
  border: none;
  color: var(--accent-color);
  cursor: pointer;
  text-decoration: underline;
  font-size: 0.85rem;
  padding: 0;
}

.filters {
  display: flex;
  align-items: end;
  gap: 12px;
  margin-bottom: 14px;
  flex-wrap: wrap;
}

.filter-group { display: flex; flex-direction: column; gap: 4px; }
.filter-group label {
  font-size: 0.78rem;
  color: var(--text-secondary);
  font-weight: 500;
}

.filter-select {
  padding: 7px 10px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
  background: var(--input-bg, var(--bg-tertiary));
  color: var(--text-primary);
  font-size: 0.88rem;
  min-width: 130px;
  font-family: inherit;
  cursor: pointer;
}
.filter-select:focus {
  outline: none;
  border-color: var(--accent-color);
  box-shadow: 0 0 0 3px var(--accent-soft);
}

.refresh-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 7px 14px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
  color: var(--text-primary);
  font-size: 0.85rem;
  cursor: pointer;
  transition: all var(--transition);
}
.refresh-btn:hover:not(:disabled) {
  background: var(--accent-soft);
  border-color: var(--accent-color);
  color: var(--accent-color);
}
.refresh-btn:disabled { opacity: 0.6; cursor: not-allowed; }

.list-area {
  flex: 1;
  display: flex;
  min-height: 0;
  flex-direction: column;
}

/* ===== Preview ===== */
.preview-mask {
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

.preview-box {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: 24px;
  width: 640px;
  max-width: 92vw;
  max-height: 85vh;
  overflow-y: auto;
  box-shadow: var(--shadow-lg);
  animation: fadeInUp 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

.preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.preview-header h3 { margin: 0; color: var(--text-primary); font-size: 1.05rem; font-weight: 600; }
.close-btn {
  background: transparent;
  border: none;
  color: var(--text-secondary);
  font-size: 1.2rem;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 6px;
}
.close-btn:hover { background: var(--bg-tertiary); color: var(--text-primary); }

.preview-doc-meta { margin: 0; color: var(--text-primary); font-size: 0.9rem; }
.preview-doc-hint { margin: 4px 0 16px; color: var(--text-muted); font-size: 0.8rem; }

.preview-loading,
.preview-error,
.preview-empty {
  text-align: center;
  padding: 30px 16px;
  color: var(--text-secondary);
  background: var(--bg-tertiary);
  border-radius: var(--radius);
}
.preview-error { color: #ef4444; }
.empty-icon { font-size: 2.4rem; opacity: 0.6; margin-bottom: 8px; }
.empty-hint { font-size: 0.8rem; color: var(--text-muted); margin-top: 4px; }

.preview-sources { display: flex; flex-direction: column; gap: 12px; }
.source-item {
  padding: 12px 14px;
  background: var(--bg-tertiary);
  border-left: 3px solid var(--accent-color);
  border-radius: var(--radius);
}
.source-header {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  font-size: 0.85rem;
  margin-bottom: 6px;
}
.source-num { font-weight: 700; color: var(--accent-color); }
.source-title { font-weight: 600; color: var(--text-primary); }
.source-meta {
  color: var(--text-secondary);
  font-size: 0.78rem;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
}
.source-score {
  margin-left: auto;
  color: var(--accent-color);
  font-variant-numeric: tabular-nums;
  font-size: 0.78rem;
  background: var(--accent-soft);
  padding: 2px 8px;
  border-radius: 10px;
}
.source-snippet {
  font-size: 0.85rem;
  color: var(--text-secondary);
  line-height: 1.55;
  white-space: pre-wrap;
}

.status-tag {
  display: inline-block;
  font-size: 0.7rem;
  padding: 1px 6px;
  border-radius: 8px;
  font-weight: 500;
  margin-left: 4px;
  vertical-align: middle;
}
.status-tag.current {
  background: rgba(34, 197, 94, 0.15);
  color: #16a34a;
}
.status-tag.repealed {
  background: rgba(239, 68, 68, 0.15);
  color: #ef4444;
}
</style>
