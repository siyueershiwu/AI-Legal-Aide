import client from './client'
import type {
  DocTypeEnum,
  KnowledgeDocument,
  KnowledgePreviewResponse,
  KnowledgeRebuildResponse,
  KnowledgeStats,
  LawCodeEnum,
} from '@/types/api'

// 后端原始响应结构（与 KnowledgeDocumentOut 对齐）
interface RawKnowledgeDocument {
  id: string
  title: string
  law_code: string
  doc_type: string
  version: string
  is_current: boolean
  effective_date: string | null
  repealed_date: string | null
  issuing_body: string | null
  article_range: string | null
  source_type: string
  file_id: string | null
  chunk_count: number
  char_count: number
  owner_id: string | null
  created_at: string
  updated_at: string
}

function toKnowledgeDocument(raw: RawKnowledgeDocument): KnowledgeDocument {
  return {
    id: raw.id,
    title: raw.title,
    law_code: raw.law_code as LawCodeEnum,
    doc_type: raw.doc_type as DocTypeEnum,
    version: raw.version,
    is_current: raw.is_current,
    effective_date: raw.effective_date,
    repealed_date: raw.repealed_date,
    issuing_body: raw.issuing_body,
    article_range: raw.article_range,
    source_type: raw.source_type as KnowledgeDocument['source_type'],
    file_id: raw.file_id,
    chunk_count: raw.chunk_count,
    char_count: raw.char_count,
    owner_id: raw.owner_id,
    created_at: raw.created_at,
    updated_at: raw.updated_at,
  }
}

export interface ListDocumentsParams {
  law_code?: LawCodeEnum
  doc_type?: DocTypeEnum
  is_current?: boolean
  limit?: number
  offset?: number
}

export async function listDocuments(
  params?: ListDocumentsParams,
): Promise<KnowledgeDocument[]> {
  const { data } = await client.get<{ documents: RawKnowledgeDocument[]; total: number }>(
    '/knowledge/documents',
    { params },
  )
  return (data.documents || []).map(toKnowledgeDocument)
}

export interface CreateDocumentPayload {
  file_id: string
  title: string
  law_code: LawCodeEnum
  doc_type: DocTypeEnum
  version?: string
  is_current?: boolean
  effective_date?: string | null
  repealed_date?: string | null
  issuing_body?: string | null
  article_range?: string | null
  source_type?: KnowledgeDocument['source_type']
}

export async function createDocument(
  payload: CreateDocumentPayload,
): Promise<KnowledgeDocument> {
  const { data } = await client.post<RawKnowledgeDocument>('/knowledge/documents', payload)
  return toKnowledgeDocument(data)
}

export async function deleteDocument(id: string): Promise<void> {
  await client.delete(`/knowledge/documents/${id}`)
}

export async function batchDelete(ids: string[]): Promise<{
  success: number
  failed: string[]
  total: number
}> {
  const { data } = await client.post<{
    success: number
    failed: string[]
    total: number
  }>('/knowledge/documents/batch-delete', { ids })
  return data
}

export async function rebuild(): Promise<KnowledgeRebuildResponse> {
  const { data } = await client.post<KnowledgeRebuildResponse>('/knowledge/rebuild')
  return data
}

export async function getStats(): Promise<KnowledgeStats> {
  const { data } = await client.get<KnowledgeStats>('/knowledge/stats')
  return data
}

export interface PreviewSearchParams {
  q: string
  law_code?: LawCodeEnum
  doc_type?: DocTypeEnum
  include_repealed?: boolean
  top_k?: number
}

export async function previewSearch(
  params: PreviewSearchParams,
): Promise<KnowledgePreviewResponse> {
  const { data } = await client.get<KnowledgePreviewResponse>(
    '/knowledge/preview-search',
    { params },
  )
  return data
}

export interface KnowledgeMeta {
  law_codes: string[]
  doc_types: string[]
  source_types: string[]
}

export async function getMeta(): Promise<KnowledgeMeta> {
  const { data } = await client.get<KnowledgeMeta>('/knowledge/meta')
  return data
}
