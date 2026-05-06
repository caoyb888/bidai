/* ============================================================
 * 投标项目相关类型定义
 * 对齐后端 project-service DTO（Java Record → TypeScript Interface）
 * ============================================================ */

/** 项目状态枚举 */
export type ProjectStatus =
  | 'DRAFT'
  | 'IN_PROGRESS'
  | 'REVIEWING'
  | 'APPROVED'
  | 'SUBMITTED'
  | 'COMPLETED'
  | 'CANCELLED'
  | 'ARCHIVED'

/** 状态标签映射 */
export const PROJECT_STATUS_LABELS: Record<ProjectStatus, string> = {
  DRAFT: '草稿',
  IN_PROGRESS: '进行中',
  REVIEWING: '审核中',
  APPROVED: '已审批',
  SUBMITTED: '已递交',
  COMPLETED: '已完成',
  CANCELLED: '已取消',
  ARCHIVED: '已归档',
}

/** 状态标签颜色映射 */
export const PROJECT_STATUS_TYPES: Record<
  ProjectStatus,
  '' | 'success' | 'warning' | 'danger' | 'info' | 'primary'
> = {
  DRAFT: 'info',
  IN_PROGRESS: 'primary',
  REVIEWING: 'warning',
  APPROVED: 'success',
  SUBMITTED: 'success',
  COMPLETED: 'success',
  CANCELLED: 'danger',
  ARCHIVED: 'info',
}

/** 项目成员 */
export interface ProjectMember {
  userId: string
  username: string
  realName: string
  projectRole: 'LEADER' | 'WRITER' | 'REVIEWER' | 'OBSERVER'
  joinedAt: string
}

/** 项目列表项（ProjectBrief） */
export interface ProjectBrief {
  id: string
  name: string
  client: string
  status: ProjectStatus
  tenderDate: string
  budgetAmount: string
  industry: string
  winRateScore: number
}

/** 项目详情（ProjectDetail） */
export interface ProjectDetail {
  id: string
  name: string
  client: string
  status: ProjectStatus
  tenderDate: string
  budgetAmount: string
  industry: string
  region: string
  description: string
  tenderAgency: string
  winRateScore: number
  members: ProjectMember[]
  createdBy: string
  createdAt: string
  updatedAt: string
}

/** 创建项目请求 */
export interface ProjectCreateRequest {
  name: string
  client: string
  industry?: string
  region?: string
  tenderDate: string
  budgetAmount?: string
  tenderAgency?: string
  description?: string
  deadline: string
}

/** 更新项目请求 */
export interface ProjectUpdateRequest {
  name?: string
  client?: string
  industry?: string
  region?: string
  tenderDate?: string
  budgetAmount?: string
  status?: ProjectStatus
  tenderAgency?: string
  description?: string
}

/** 分页响应 */
export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  pageSize: number
  totalPages: number
}

/** 项目列表查询参数 */
export interface ProjectListParams {
  page?: number
  pageSize?: number
  status?: ProjectStatus
  industry?: string
  keyword?: string
  tenderDateFrom?: string
  tenderDateTo?: string
  myProjectsOnly?: boolean
}
