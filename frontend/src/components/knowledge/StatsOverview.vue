<script setup lang="ts">
import { computed } from 'vue'
import { useKnowledgeStore } from '@/stores/knowledge'
import { LAW_CODE_LABELS, type LawCodeEnum } from '@/types/api'

const kb = useKnowledgeStore()

// 重点收录法律（出现次数最多的）
const topLaw = computed(() => {
  if (!kb.stats || !kb.stats.by_law_code) return '—'
  const entries = Object.entries(kb.stats.by_law_code)
  if (entries.length === 0) return '—'
  entries.sort((a, b) => b[1] - a[1])
  const [code] = entries[0] as [string, number]
  return LAW_CODE_LABELS[code as LawCodeEnum] ?? code
})

// 现行 / 废止
const currentCount = computed(() => kb.stats?.current_count ?? 0)
const repealedCount = computed(() => kb.stats?.repealed_count ?? 0)
const hasRepealed = computed(() => repealedCount.value > 0)
</script>

<template>
  <div class="stats-overview">
    <div class="stat-card">
      <div class="stat-icon stat-icon-purple">📄</div>
      <div class="stat-body">
        <div class="stat-value">{{ kb.stats?.total_documents ?? '—' }}</div>
        <div class="stat-label">总文档数</div>
      </div>
    </div>
    <div class="stat-card">
      <div class="stat-icon stat-icon-blue">🧩</div>
      <div class="stat-body">
        <div class="stat-value">{{ kb.stats?.total_chunks ?? '—' }}</div>
        <div class="stat-label">总切片数（按条）</div>
      </div>
    </div>
    <div class="stat-card">
      <div class="stat-icon stat-icon-green">📗</div>
      <div class="stat-body">
        <div class="stat-value">{{ currentCount }}</div>
        <div class="stat-label">现行有效文档</div>
      </div>
    </div>
    <div v-if="hasRepealed" class="stat-card">
      <div class="stat-icon stat-icon-rose">📕</div>
      <div class="stat-body">
        <div class="stat-value">{{ repealedCount }}</div>
        <div class="stat-label">已废止文档（保留备查）</div>
      </div>
    </div>
    <div class="stat-card">
      <div class="stat-icon stat-icon-amber">📜</div>
      <div class="stat-body">
        <div class="stat-value">{{ topLaw }}</div>
        <div class="stat-label">重点收录法律</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.stats-overview {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: 14px;
  margin-bottom: 20px;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 18px 20px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  transition: all var(--transition);
}

.stat-card:hover {
  box-shadow: var(--shadow);
  transform: translateY(-1px);
  border-color: var(--accent-soft);
}

.stat-icon {
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.5rem;
  border-radius: var(--radius);
  flex-shrink: 0;
}

.stat-icon-purple { background: var(--accent-soft); }
.stat-icon-blue { background: rgba(59, 130, 246, 0.12); }
.stat-icon-green { background: rgba(34, 197, 94, 0.12); }
.stat-icon-rose { background: rgba(239, 68, 68, 0.12); }
.stat-icon-amber { background: rgba(245, 158, 11, 0.12); }

.stat-body { display: flex; flex-direction: column; min-width: 0; }
.stat-value {
  font-size: 1.4rem;
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.2;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.stat-label {
  font-size: 0.8rem;
  color: var(--text-secondary);
  margin-top: 2px;
}
</style>
