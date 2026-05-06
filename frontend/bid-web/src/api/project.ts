import apiClient from './index'
import type {
  ApiResponse,
  PaginatedResponse,
  ProjectBrief,
  ProjectDetail,
  ProjectCreateRequest,
  ProjectUpdateRequest,
  ProjectListParams,
  ProjectMember,
} from '@/types'

export const projectService = {
  /** 获取项目列表（支持分页与筛选） */
  async listProjects(params: ProjectListParams = {}): Promise<PaginatedResponse<ProjectBrief>> {
    const res = await apiClient.get<ApiResponse<PaginatedResponse<ProjectBrief>>>('/projects', {
      params: {
        page: params.page ?? 1,
        page_size: params.pageSize ?? 20,
        status: params.status,
        industry: params.industry,
        keyword: params.keyword,
        tender_date_from: params.tenderDateFrom,
        tender_date_to: params.tenderDateTo,
        my_projects_only: params.myProjectsOnly,
      },
    })
    return res.data.data
  },

  /** 获取项目详情 */
  async getProject(id: string): Promise<ProjectDetail> {
    const res = await apiClient.get<ApiResponse<ProjectDetail>>(`/projects/${id}`)
    return res.data.data
  },

  /** 创建项目 */
  async createProject(data: ProjectCreateRequest): Promise<ProjectDetail> {
    const res = await apiClient.post<ApiResponse<ProjectDetail>>('/projects', data)
    return res.data.data
  },

  /** 更新项目 */
  async updateProject(id: string, data: ProjectUpdateRequest): Promise<ProjectDetail> {
    const res = await apiClient.put<ApiResponse<ProjectDetail>>(`/projects/${id}`, data)
    return res.data.data
  },

  /** 删除（归档）项目 */
  async deleteProject(id: string): Promise<void> {
    await apiClient.delete<ApiResponse<null>>(`/projects/${id}`)
  },

  /** 获取项目成员 */
  async getProjectMembers(id: string): Promise<ProjectMember[]> {
    const res = await apiClient.get<ApiResponse<ProjectMember[]>>(`/projects/${id}/members`)
    return res.data.data
  },
}
