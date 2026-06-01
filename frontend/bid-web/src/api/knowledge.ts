import apiClient from './index'
import type {
  ApiResponse,
  PaginatedResponse,
  KnowledgeDocument,
  KnowledgeListParams,
  KnowledgeUploadResponse,
  KnowledgeStatsResponse,
  TaskDetail,
} from '@/types'

export const knowledgeService = {
  /** 获取知识库文档列表（支持分页与筛选） */
  async listDocuments(params: KnowledgeListParams = {}): Promise<PaginatedResponse<KnowledgeDocument>> {
    const res = await apiClient.get<ApiResponse<PaginatedResponse<KnowledgeDocument>>>('/knowledge/documents', {
      params: {
        page: params.page ?? 1,
        page_size: params.pageSize ?? 20,
        doc_category: params.doc_category,
        tags: params.tags?.join(','),
        is_expired: params.is_expired,
        keyword: params.keyword,
      },
    })
    return res.data.data
  },

  /** 删除知识库文档（软删除） */
  async deleteDocument(id: string): Promise<void> {
    await apiClient.delete<ApiResponse<null>>(`/knowledge/documents/${id}`)
  },

  /** 获取知识库统计信息 */
  async getStats(): Promise<KnowledgeStatsResponse> {
    const res = await apiClient.get<ApiResponse<KnowledgeStatsResponse>>('/knowledge/stats')
    return res.data.data
  },

  /** 上传文档入库 */
  async uploadDocument(formData: FormData): Promise<KnowledgeUploadResponse> {
    const res = await apiClient.post<ApiResponse<KnowledgeUploadResponse>>('/knowledge/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
    return res.data.data
  },

  /** 查询异步任务状态 */
  async getTaskStatus(taskId: string): Promise<TaskDetail> {
    const res = await apiClient.get<ApiResponse<TaskDetail>>(`/tasks/${taskId}`)
    return res.data.data
  },
}
