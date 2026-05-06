import apiClient from './index'
import type { ApiResponse, LoginRequest, LoginResponse, UserInfo } from '@/types'

export const authService = {
  async login(data: LoginRequest): Promise<LoginResponse> {
    const res = await apiClient.post<ApiResponse<LoginResponse>>('/auth/login', data)
    return res.data.data
  },

  async logout(): Promise<void> {
    await apiClient.post<ApiResponse<null>>('/auth/logout')
  },

  async refreshToken(): Promise<LoginResponse> {
    const res = await apiClient.post<ApiResponse<LoginResponse>>('/auth/refresh')
    return res.data.data
  },

  async getCurrentUser(): Promise<UserInfo> {
    const res = await apiClient.get<ApiResponse<UserInfo>>('/auth/me')
    return res.data.data
  },
}
