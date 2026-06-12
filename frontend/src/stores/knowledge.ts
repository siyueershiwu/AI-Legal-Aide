import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as api from '@/api/knowledge'
import type {
  DocTypeEnum,
  KnowledgeDocument,
  KnowledgeStats,
  LawCodeEnum,
} from '@/types/api'

export const useKnowledgeStore = defineStore('knowledge', () => {
  // ===== 状态 =====
  const documents = ref<KnowledgeDocument[]>([])
  const stats = ref<KnowledgeStats | null>(null)
  const meta = ref<{ law_codes: string[]; doc_types: string[]; source_types: string[] } | null>(null)

  const loading = ref(false)         // 列表 / 统计 加载
  const uploading = ref(false)       // 入库中（文件 + 元数据两步合起来算一次上传）
  const rebuilding = ref(false)      // 清空重建中（可能耗时长）
  const error = ref<string>('')

  // 过滤器
  const filterLawCode = ref<LawCodeEnum | ''>('')
  const filterDocType = ref<DocTypeEnum | ''>('')
  // 现行 / 废止 / 全部
  const filterStatus = ref<'all' | 'current' | 'repealed'>('all')

  // ===== 内部 =====
  function clearError(): void {
    error.value = ''
  }

  function setError(msg: string): void {
    error.value = msg
  }

  // ===== 列表 / 统计 =====
  async function loadDocuments(): Promise<void> {
    loading.value = true
    clearError()
    try {
      const params: api.ListDocumentsParams = {}
      if (filterLawCode.value) params.law_code = filterLawCode.value
      if (filterDocType.value) params.doc_type = filterDocType.value
      if (filterStatus.value === 'current') params.is_current = true
      else if (filterStatus.value === 'repealed') params.is_current = false
      documents.value = await api.listDocuments(params)
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } }; message?: string })
      setError(msg?.response?.data?.detail || msg?.message || '加载文档列表失败')
      documents.value = []
    } finally {
      loading.value = false
    }
  }

  async function loadStats(): Promise<void> {
    try {
      stats.value = await api.getStats()
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } }; message?: string })
      setError(msg?.response?.data?.detail || msg?.message || '加载统计失败')
    }
  }

  async function loadMeta(): Promise<void> {
    try {
      meta.value = await api.getMeta()
    } catch (e: unknown) {
      // meta 失败不致命（前端可以硬编码回退），只 log
      console.warn('loadMeta failed', e)
    }
  }

  function setFilter(
    lawCode: LawCodeEnum | '',
    docType: DocTypeEnum | '',
    status: 'all' | 'current' | 'repealed' = 'all',
  ): void {
    filterLawCode.value = lawCode
    filterDocType.value = docType
    filterStatus.value = status
    void loadDocuments()
  }

  // ===== 入库（两步走：先上传文件，再入库） =====
  async function uploadDocument(
    uploadFn: () => Promise<{ id: string }>,
    payload: Omit<api.CreateDocumentPayload, 'file_id'>,
  ): Promise<KnowledgeDocument> {
    uploading.value = true
    clearError()
    try {
      const file = await uploadFn()
      const doc = await api.createDocument({ ...payload, file_id: file.id })
      // 头部插入（最新上传的看上面）
      documents.value = [doc, ...documents.value]
      // 异步刷新统计（不阻塞）
      void loadStats()
      return doc
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } }; message?: string })
      const detail = msg?.response?.data?.detail || msg?.message || '入库失败'
      setError(detail)
      throw new Error(detail)
    } finally {
      uploading.value = false
    }
  }

  // ===== 删除 =====
  async function deleteDocument(id: string): Promise<void> {
    clearError()
    try {
      await api.deleteDocument(id)
      documents.value = documents.value.filter((d) => d.id !== id)
      void loadStats()
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } }; message?: string })
      setError(msg?.response?.data?.detail || msg?.message || '删除失败')
      throw e
    }
  }

  async function batchDelete(ids: string[]): Promise<{
    success: number
    failed: string[]
  }> {
    clearError()
    try {
      const result = await api.batchDelete(ids)
      // 刷新列表
      await loadDocuments()
      void loadStats()
      return { success: result.success, failed: result.failed }
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } }; message?: string })
      setError(msg?.response?.data?.detail || msg?.message || '批量删除失败')
      throw e
    }
  }

  // ===== 清空重建 =====
  async function rebuild(): Promise<void> {
    rebuilding.value = true
    clearError()
    try {
      await api.rebuild()
      await loadDocuments()
      await loadStats()
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } }; message?: string })
      setError(msg?.response?.data?.detail || msg?.message || '重建失败')
      throw e
    } finally {
      rebuilding.value = false
    }
  }

  // ===== 检索预览 =====
  async function previewSearch(
    q: string,
    lawCode?: LawCodeEnum,
    docType?: DocTypeEnum,
    topK = 5,
    includeRepealed = false,
  ): Promise<import('@/types/api').KnowledgePreviewResponse> {
    return await api.previewSearch({
      q,
      law_code: lawCode,
      doc_type: docType,
      top_k: topK,
      include_repealed: includeRepealed,
    })
  }

  return {
    // 状态
    documents,
    stats,
    meta,
    loading,
    uploading,
    rebuilding,
    error,
    filterLawCode,
    filterDocType,
    filterStatus,
    // 操作
    clearError,
    loadDocuments,
    loadStats,
    loadMeta,
    setFilter,
    uploadDocument,
    deleteDocument,
    batchDelete,
    rebuild,
    previewSearch,
  }
})
