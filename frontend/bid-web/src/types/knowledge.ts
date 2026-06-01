/* ============================================================
 * 知识库模块类型定义
 * 对齐后端 knowledge-service DTO（Python Pydantic → TypeScript Interface）
 * ============================================================ */

/** 文档分类枚举 */
export type DocCategory =
  | 'QUALIFICATION'
  | 'PERFORMANCE'
  | 'PERSONNEL'
  | 'SOLUTION_TEMPLATE'
  | 'GENERAL'

/** 文档分类中文映射 */
export const DOC_CATEGORY_LABELS: Record<DocCategory, string> = {
  QUALIFICATION: '资质证书',
  PERFORMANCE: '业绩案例',
  PERSONNEL: '人员信息',
  SOLUTION_TEMPLATE: '方案模板',
  GENERAL: '通用资料',
}

/** 文档分类标签颜色映射 */
export const DOC_CATEGORY_TYPES: Record<
  DocCategory,
  '' | 'success' | 'warning' | 'danger' | 'info' | 'primary'
> = {
  QUALIFICATION: 'success',
  PERFORMANCE: 'primary',
  PERSONNEL: 'warning',
  SOLUTION_TEMPLATE: 'info',
  GENERAL: '',
}

/** 入库模式枚举 */
export type IngestMode = 'AUTO' | 'MANUAL_CONFIRM' | 'MANUAL'

/** 入库模式中文映射 */
export const INGEST_MODE_LABELS: Record<IngestMode, string> = {
  AUTO: '自动入库',
  MANUAL_CONFIRM: '人工确认',
  MANUAL: '手动录入',
}

/** 任务状态枚举 */
export type TaskStatus = 'PENDING' | 'RUNNING' | 'SUCCESS' | 'FAILED' | 'CANCELLED' | 'RETRYING'

/** 任务状态中文映射 */
export const TASK_STATUS_LABELS: Record<TaskStatus, string> = {
  PENDING: '等待中',
  RUNNING: '处理中',
  SUCCESS: '已完成',
  FAILED: '失败',
  CANCELLED: '已取消',
  RETRYING: '重试中',
}

/** 任务状态标签颜色映射 */
export const TASK_STATUS_TYPES: Record<
  TaskStatus,
  '' | 'success' | 'warning' | 'danger' | 'info' | 'primary'
> = {
  PENDING: 'info',
  RUNNING: 'primary',
  SUCCESS: 'success',
  FAILED: 'danger',
  CANCELLED: 'info',
  RETRYING: 'warning',
}

/** 知识库文档 */
export interface KnowledgeDocument {
  id: string
  title: string
  doc_category: DocCategory
  tags: string[]
  file_type: string
  page_count: number
  confidence: number
  ingest_mode: IngestMode
  is_expired: boolean
  created_at: string
}

/** 知识库文档列表查询参数 */
export interface KnowledgeListParams {
  page?: number
  pageSize?: number
  doc_category?: DocCategory
  tags?: string[]
  is_expired?: boolean
  keyword?: string
}

/** 知识库上传响应 */
export interface KnowledgeUploadResponse {
  task_id: string
  status: TaskStatus
  poll_url: string
  estimated_seconds?: number
  document_id?: string
  is_duplicate: boolean
}

/** 分类统计项 */
export interface CategoryStat {
  category: string
  count: number
  expired_count: number
}

/** 即将过期项 */
export interface ExpiringSoonItem {
  doc_id: string
  title: string
  expire_date: string
}

/** 知识库统计响应 */
export interface KnowledgeStatsResponse {
  total_documents: number
  health_score: number
  category_stats: CategoryStat[]
  expiring_soon: ExpiringSoonItem[]
}

/** 异步任务详情 */
export interface TaskDetail {
  task_id: string
  task_type: string
  status: TaskStatus
  progress: number
  result_url?: string
  error_message?: string | null
  queued_at: string
  started_at?: string | null
  completed_at?: string | null
  duration_ms?: number | null
}

/** 上传进度跟踪项（前端内部使用） */
export interface UploadProgressItem {
  taskId: string
  fileName: string
  status: TaskStatus
  progress: number
  errorMessage?: string
  documentId?: string
  isDuplicate?: boolean
}
