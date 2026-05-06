import 'vue-router'

/* ============================================================
 * API 通用响应包装
 * ============================================================ */
export interface ApiResponse<T> {
  code: number
  message: string
  data: T
  requestId: string
}

/* ============================================================
 * 认证相关
 * ============================================================ */
export interface LoginRequest {
  username: string
  password: string
}

export interface LoginResponse {
  accessToken: string
  expiresIn: number
}

export interface UserInfo {
  id: string
  username: string
  realName: string
  roles: string[]
  permissions: string[]
}

/* ============================================================
 * 项目相关类型（从子模块聚合导出，便于 api 层统一导入）
 * ============================================================ */
export type {
  ProjectBrief,
  ProjectDetail,
  ProjectMember,
  ProjectCreateRequest,
  ProjectUpdateRequest,
  ProjectListParams,
  PaginatedResponse,
  ProjectStatus,
} from './project'

/* ============================================================
 * 路由元信息扩展（供 Vue Router 权限守卫使用）
 * ============================================================ */
declare module 'vue-router' {
  interface RouteMeta {
    /** 是否免登录访问 */
    public?: boolean
    /** 访问所需权限码，如 project:read */
    permission?: string
    /** 页面标题（用于菜单与面包屑） */
    title?: string
  }
}
