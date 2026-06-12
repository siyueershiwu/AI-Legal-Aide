import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useKnowledgeStore } from '@/stores/knowledge'
import type { KnowledgeDocument, KnowledgeStats } from '@/types/api'

// Mock @/api/knowledge
vi.mock('@/api/knowledge', () => ({
  listDocuments: vi.fn(),
  getStats: vi.fn(),
  getMeta: vi.fn(),
  createDocument: vi.fn(),
  deleteDocument: vi.fn(),
  batchDelete: vi.fn(),
  rebuild: vi.fn(),
  previewSearch: vi.fn(),
}))

import * as api from '@/api/knowledge'

const fakeDoc: KnowledgeDocument = {
  id: 'doc-1',
  title: '中华人民共和国民法典',
  law_code: '民法典',
  doc_type: 'statute',
  version: '2021',
  is_current: true,
  effective_date: '2021-01-01',
  repealed_date: null,
  issuing_body: '全国人民代表大会',
  article_range: '第1条 - 第1260条',
  source_type: 'upload',
  file_id: 'f-1',
  chunk_count: 1260,
  char_count: 120000,
  owner_id: 'u-1',
  created_at: '2025-01-01T00:00:00Z',
  updated_at: '2025-01-01T00:00:00Z',
}

const fakeStats: KnowledgeStats = {
  total_documents: 10,
  total_chunks: 42,
  total_characters: 100000,
  by_law_code: { 民法典: 5, 刑法: 3 },
  by_doc_type: { statute: 4, interpretation: 6 },
  current_count: 8,
  repealed_count: 2,
}

describe('useKnowledgeStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  describe('loadDocuments', () => {
    it('成功时填入 documents', async () => {
      vi.mocked(api.listDocuments).mockResolvedValue([fakeDoc])

      const kb = useKnowledgeStore()
      await kb.loadDocuments()

      expect(kb.documents).toHaveLength(1)
      expect(kb.documents[0]?.id).toBe('doc-1')
      expect(kb.error).toBe('')
      expect(kb.loading).toBe(false)
    })

    it('失败时设置 error 并清空列表', async () => {
      vi.mocked(api.listDocuments).mockRejectedValue(new Error('network down'))

      const kb = useKnowledgeStore()
      await kb.loadDocuments()

      expect(kb.error).toContain('network down')
      expect(kb.documents).toHaveLength(0)
      expect(kb.loading).toBe(false)
    })

    it('带 law_code/doc_type 过滤时透传给 API', async () => {
      vi.mocked(api.listDocuments).mockResolvedValue([fakeDoc])

      const kb = useKnowledgeStore()
      kb.filterLawCode = '民法典'
      kb.filterDocType = 'statute'
      await kb.loadDocuments()

      expect(api.listDocuments).toHaveBeenCalledWith({
        law_code: '民法典',
        doc_type: 'statute',
      })
    })

    it('filterStatus=current 时透传 is_current=true', async () => {
      vi.mocked(api.listDocuments).mockResolvedValue([])

      const kb = useKnowledgeStore()
      kb.filterStatus = 'current'
      await kb.loadDocuments()

      expect(api.listDocuments).toHaveBeenCalledWith({ is_current: true })
    })

    it('filterStatus=repealed 时透传 is_current=false', async () => {
      vi.mocked(api.listDocuments).mockResolvedValue([])

      const kb = useKnowledgeStore()
      kb.filterStatus = 'repealed'
      await kb.loadDocuments()

      expect(api.listDocuments).toHaveBeenCalledWith({ is_current: false })
    })
  })

  describe('loadStats', () => {
    it('填入 stats', async () => {
      vi.mocked(api.getStats).mockResolvedValue(fakeStats)

      const kb = useKnowledgeStore()
      await kb.loadStats()

      expect(kb.stats?.total_documents).toBe(10)
      expect(kb.stats?.by_law_code.民法典).toBe(5)
      expect(kb.stats?.current_count).toBe(8)
      expect(kb.stats?.repealed_count).toBe(2)
    })
  })

  describe('uploadDocument', () => {
    it('成功：插入新 doc 到列表头部并清掉 uploading', async () => {
      vi.mocked(api.createDocument).mockResolvedValue(fakeDoc)
      const uploadFn = vi.fn().mockResolvedValue({ id: 'f-1' })

      const kb = useKnowledgeStore()
      const result = await kb.uploadDocument(uploadFn, {
        title: '中华人民共和国民法典',
        law_code: '民法典',
        doc_type: 'statute',
      })

      expect(result.id).toBe('doc-1')
      expect(kb.documents[0]?.id).toBe('doc-1')
      expect(kb.uploading).toBe(false)
      expect(uploadFn).toHaveBeenCalledOnce()
    })

    it('失败：抛错，error 被设置，uploading 恢复', async () => {
      vi.mocked(api.createDocument).mockRejectedValue(new Error('ingest failed'))
      const uploadFn = vi.fn().mockResolvedValue({ id: 'f-1' })

      const kb = useKnowledgeStore()
      await expect(
        kb.uploadDocument(uploadFn, {
          title: 't',
          law_code: '民法典',
          doc_type: 'statute',
        }),
      ).rejects.toThrow('ingest failed')

      expect(kb.error).toBe('ingest failed')
      expect(kb.uploading).toBe(false)
    })
  })

  describe('deleteDocument', () => {
    it('成功：从列表移除', async () => {
      vi.mocked(api.deleteDocument).mockResolvedValue(undefined)

      const kb = useKnowledgeStore()
      kb.documents = [fakeDoc, { ...fakeDoc, id: 'doc-2' }]
      await kb.deleteDocument('doc-1')

      expect(kb.documents).toHaveLength(1)
      expect(kb.documents[0]?.id).toBe('doc-2')
    })

    it('失败：抛错并设置 error', async () => {
      vi.mocked(api.deleteDocument).mockRejectedValue(new Error('not found'))

      const kb = useKnowledgeStore()
      kb.documents = [fakeDoc]
      await expect(kb.deleteDocument('doc-1')).rejects.toThrow('not found')

      expect(kb.error).toBe('not found')
      expect(kb.documents).toHaveLength(1)
    })
  })

  describe('batchDelete', () => {
    it('成功：刷新列表', async () => {
      vi.mocked(api.batchDelete).mockResolvedValue({ success: 2, failed: [], total: 2 })
      vi.mocked(api.listDocuments).mockResolvedValue([])

      const kb = useKnowledgeStore()
      kb.documents = [fakeDoc, { ...fakeDoc, id: 'doc-2' }]
      const result = await kb.batchDelete(['doc-1', 'doc-2'])

      expect(result.success).toBe(2)
      expect(api.listDocuments).toHaveBeenCalledOnce()
    })
  })

  describe('rebuild', () => {
    it('成功：刷新列表 + 统计', async () => {
      vi.mocked(api.rebuild).mockResolvedValue({ success: 1, failed: 0, errors: [] })
      vi.mocked(api.listDocuments).mockResolvedValue([])
      vi.mocked(api.getStats).mockResolvedValue(fakeStats)

      const kb = useKnowledgeStore()
      await kb.rebuild()

      expect(api.rebuild).toHaveBeenCalledOnce()
      expect(kb.rebuilding).toBe(false)
    })

    it('失败：rebuilding 恢复 false', async () => {
      vi.mocked(api.rebuild).mockRejectedValue(new Error('rebuild fail'))

      const kb = useKnowledgeStore()
      await expect(kb.rebuild()).rejects.toThrow('rebuild fail')
      expect(kb.rebuilding).toBe(false)
      expect(kb.error).toBe('rebuild fail')
    })
  })

  describe('setFilter', () => {
    it('设置后触发 loadDocuments', async () => {
      vi.mocked(api.listDocuments).mockResolvedValue([])

      const kb = useKnowledgeStore()
      await kb.setFilter('刑法', 'interpretation', 'current')

      expect(kb.filterLawCode).toBe('刑法')
      expect(kb.filterDocType).toBe('interpretation')
      expect(kb.filterStatus).toBe('current')
      expect(api.listDocuments).toHaveBeenCalledWith({
        law_code: '刑法',
        doc_type: 'interpretation',
        is_current: true,
      })
    })
  })

  describe('previewSearch', () => {
    it('直接透传', async () => {
      const fake = {
        sources: [{
          title: 'A',
          law_code: '民法典',
          doc_type: 'statute',
          version: '2021',
          is_current: true,
          article_no: '1',
          score: 0.9,
          snippet: 's',
        }],
      }
      vi.mocked(api.previewSearch).mockResolvedValue(fake)

      const kb = useKnowledgeStore()
      const r = await kb.previewSearch('借款', '民法典', 'statute', 3)
      expect(r).toBe(fake)
      expect(api.previewSearch).toHaveBeenCalledWith({
        q: '借款',
        law_code: '民法典',
        doc_type: 'statute',
        top_k: 3,
        include_repealed: false,
      })
    })
  })

  describe('clearError', () => {
    it('清空 error', () => {
      const kb = useKnowledgeStore()
      kb.error = 'something'
      kb.clearError()
      expect(kb.error).toBe('')
    })
  })
})
