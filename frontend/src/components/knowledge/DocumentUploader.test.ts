import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { mount, flushPromises } from '@vue/test-utils'
import DocumentUploader from '@/components/knowledge/DocumentUploader.vue'

// Mock @/api/knowledge
vi.mock('@/api/knowledge', () => ({
  createDocument: vi.fn(),
  listDocuments: vi.fn(),
  getStats: vi.fn(),
  getMeta: vi.fn().mockResolvedValue({ law_codes: [], doc_types: [], source_types: [] }),
  deleteDocument: vi.fn(),
  batchDelete: vi.fn(),
  rebuild: vi.fn(),
  previewSearch: vi.fn(),
}))

// Mock @/api/files - upload 走真实 axios 会打到 jsdom 的 network 失败
vi.mock('@/api/files', () => ({
  uploadFile: vi.fn().mockImplementation(async (file: File) => ({
    id: 'f-1',
    url: 'http://test/f-1',
    type: file.type,
    name: file.name,
    size: file.size,
  })),
}))

import * as api from '@/api/knowledge'

// Teleport 把内容移出 wrapper；用 attachTo: document.body 才能在 document 上找
function mountInBody() {
  return mount(DocumentUploader, { attachTo: document.body })
}

function findByText(wrapper: ReturnType<typeof mount>, text: string) {
  // Teleport 后要从整个 document.body 找
  const all = document.body.querySelectorAll('button')
  for (const b of Array.from(all)) {
    if (b.textContent?.includes(text)) return b as HTMLButtonElement
  }
  return null
}

describe('DocumentUploader', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    document.body.innerHTML = ''
  })

  it('默认渲染表单字段', () => {
    const wrapper = mountInBody()
    expect(document.body.querySelector('input.text-input')).toBeTruthy()
    expect(document.body.querySelector('select')).toBeTruthy()
    wrapper.unmount()
  })

  it('未选文件时提交按钮被禁用', () => {
    const wrapper = mountInBody()
    const submitBtn = findByText(wrapper, '入库')
    expect(submitBtn).toBeTruthy()
    expect(submitBtn!.disabled).toBe(true)
    wrapper.unmount()
  })

  it('选择文件后自动填 title（去后缀）', async () => {
    const wrapper = mountInBody()
    const file = new File(['hello'], '民法典.md', { type: 'text/markdown' })
    const input = document.body.querySelector('input[type=file]') as HTMLInputElement
    Object.defineProperty(input, 'files', { value: [file] })
    input.dispatchEvent(new Event('change', { bubbles: true }))
    await flushPromises()

    const titleInput = document.body.querySelector('input.text-input') as HTMLInputElement
    expect(titleInput.value).toBe('民法典')
    wrapper.unmount()
  })

  it('取消 emit cancel 事件', async () => {
    const wrapper = mountInBody()
    const cancelBtn = findByText(wrapper, '取消')
    expect(cancelBtn).toBeTruthy()
    cancelBtn!.click()
    await flushPromises()

    expect(wrapper.emitted('cancel')).toBeTruthy()
    wrapper.unmount()
  })

  it('标题为空时即使有文件也不能提交', async () => {
    const wrapper = mountInBody()
    const file = new File(['x'], 'a.txt', { type: 'text/plain' })
    const input = document.body.querySelector('input[type=file]') as HTMLInputElement
    Object.defineProperty(input, 'files', { value: [file] })
    input.dispatchEvent(new Event('change', { bubbles: true }))
    await flushPromises()

    // 清空 title
    const titleInput = document.body.querySelector('input.text-input') as HTMLInputElement
    titleInput.value = ''
    titleInput.dispatchEvent(new Event('input', { bubbles: true }))
    await flushPromises()

    const submitBtn = findByText(wrapper, '入库')
    expect(submitBtn!.disabled).toBe(true)
    wrapper.unmount()
  })

  it('提交成功时 emit uploaded 事件', async () => {
    vi.mocked(api.createDocument).mockResolvedValue({
      id: 'doc-new',
      title: '民法典',
      law_code: '民法典',
      doc_type: 'statute',
      version: '2021',
      is_current: true,
      effective_date: '2021-01-01',
      repealed_date: null,
      issuing_body: '全国人大',
      article_range: '第1条 - 第1260条',
      source_type: 'upload',
      file_id: 'f-1',
      chunk_count: 1,
      char_count: 100,
      owner_id: 'u-1',
      created_at: '2025-01-01T00:00:00Z',
      updated_at: '2025-01-01T00:00:00Z',
    })

    const wrapper = mountInBody()

    // 选文件
    const file = new File(['content'], 'test.md', { type: 'text/markdown' })
    const fileInput = document.body.querySelector('input[type=file]') as HTMLInputElement
    Object.defineProperty(fileInput, 'files', { value: [file] })
    fileInput.dispatchEvent(new Event('change', { bubbles: true }))
    await flushPromises()

    // 填 title
    const titleInput = document.body.querySelector('input.text-input') as HTMLInputElement
    titleInput.value = '民法典'
    titleInput.dispatchEvent(new Event('input', { bubbles: true }))
    await flushPromises()

    // 提交
    const submitBtn = findByText(wrapper, '入库')
    expect(submitBtn!.disabled).toBe(false)
    submitBtn!.click()
    await flushPromises()

    expect(api.createDocument).toHaveBeenCalledOnce()
    expect(wrapper.emitted('uploaded')).toBeTruthy()
    wrapper.unmount()
  })

  it('提交失败时显示错误信息', async () => {
    vi.mocked(api.createDocument).mockRejectedValue(new Error('ingest failed'))

    const wrapper = mountInBody()
    const file = new File(['x'], 'a.md', { type: 'text/markdown' })
    const fileInput = document.body.querySelector('input[type=file]') as HTMLInputElement
    Object.defineProperty(fileInput, 'files', { value: [file] })
    fileInput.dispatchEvent(new Event('change', { bubbles: true }))
    await flushPromises()

    const titleInput = document.body.querySelector('input.text-input') as HTMLInputElement
    titleInput.value = '测试'
    titleInput.dispatchEvent(new Event('input', { bubbles: true }))
    await flushPromises()

    const submitBtn = findByText(wrapper, '入库')
    submitBtn!.click()
    await flushPromises()

    const errEl = document.body.querySelector('.form-error')
    expect(errEl).toBeTruthy()
    expect(errEl!.textContent).toContain('ingest failed')
    wrapper.unmount()
  })
})
