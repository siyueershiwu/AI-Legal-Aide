// 共享类型
export interface User {
  id: string
  username: string
  email?: string | null
  avatar?: string | null
  created_at: string
}

export interface LoginRequest {
  username: string
  password: string
}

export interface RegisterRequest {
  username: string
  password: string
  email?: string
}

export interface AuthResponse {
  success: boolean
  access_token: string
  token_type: string
  user_id: string
  username: string
}

export type Role = 'user' | 'assistant'

export interface Message {
  id: string
  role: Role
  content: string
  created_at: string
  displayedContent?: string
  isStreaming?: boolean
  loading?: boolean
  files?: Array<{ id: string; url: string; type: string; name: string }>
  image?: string | null
  sources?: KnowledgeSource[]  // RAG 引用来源
}

export interface ChatSession {
  id: string
  title: string | null
  pinned: boolean
  message_count: number
  created_at: string
  updated_at: string
}

export interface SessionDetail {
  id: string
  title: string | null
  pinned: boolean
  created_at: string
  updated_at: string
  messages: Message[]
}

export interface UploadedFile {
  id: string
  url: string
  type: string
  name: string
  size?: number
}

export interface SSEEvent {
  content?: string
  done?: boolean
  event?: 'tool_call' | 'tool_result' | 'sources'
  name?: string
  result?: unknown
  error?: string | null
  session_id?: string
  sources?: KnowledgeSource[]  // RAG 引用来源（kb_search 工具结果反解）
}

// ===== 知识库（法律 RAG）=====

export type LawCodeEnum =
  | '民法典'
  | '刑法'
  | '劳动法'
  | '劳动合同法'
  | '治安管理处罚法'
  | '个人信息保护法'
  | '网络安全法'
  | '数据安全法'
  | '宪法'
  | '行政处罚法'
  | '民事诉讼法'
  | '刑事诉讼法'
  | '公司法'
  | '其他'

export type DocTypeEnum =
  | 'statute'
  | 'interpretation'
  | 'commentary'
  | 'scenario'
  | 'boundary'
  | 'diff'
  | 'repeal_note'
  | 'other'

export type SourceTypeEnum = 'upload' | 'url' | 'manual'

// 法律名直接是中文，不需要额外映射；保留 record 是为了和原 UI 复用查表逻辑
export const LAW_CODE_LABELS: Record<LawCodeEnum, string> = {
  民法典: '民法典',
  刑法: '刑法',
  劳动法: '劳动法',
  劳动合同法: '劳动合同法',
  治安管理处罚法: '治安管理处罚法',
  个人信息保护法: '个人信息保护法',
  网络安全法: '网络安全法',
  数据安全法: '数据安全法',
  宪法: '宪法',
  行政处罚法: '行政处罚法',
  民事诉讼法: '民事诉讼法',
  刑事诉讼法: '刑事诉讼法',
  公司法: '公司法',
  其他: '其他',
}

export const DOC_TYPE_LABELS: Record<DocTypeEnum, string> = {
  statute: '法律正文',
  interpretation: '司法解释',
  commentary: '逐条释义',
  scenario: '场景适用',
  boundary: '适用边界',
  diff: '新旧对比',
  repeal_note: '废止标注',
  other: '其他资料',
}

export interface KnowledgeSource {
  title: string
  law_code: string
  doc_type: string
  version: string
  is_current: boolean
  article_no?: string | null
  score: number
  snippet: string
}

export interface KnowledgeDocument {
  id: string
  title: string
  law_code: LawCodeEnum
  doc_type: DocTypeEnum
  version: string
  is_current: boolean
  effective_date?: string | null
  repealed_date?: string | null
  issuing_body?: string | null
  article_range?: string | null
  source_type: SourceTypeEnum
  file_id?: string | null
  chunk_count: number
  char_count: number
  owner_id?: string | null
  created_at: string
  updated_at: string
}

export interface KnowledgeStats {
  total_documents: number
  total_chunks: number
  total_characters: number
  by_law_code: Record<string, number>
  by_doc_type: Record<string, number>
  current_count: number
  repealed_count: number
}

export interface KnowledgePreviewResponse {
  sources: KnowledgeSource[]
}

export interface KnowledgeRebuildResponse {
  success: number
  failed: number
  errors: string[]
}
