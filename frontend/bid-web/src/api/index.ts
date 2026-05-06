import axios, {
  type AxiosInstance,
  type AxiosResponse,
  type InternalAxiosRequestConfig,
} from 'axios'
import type { ApiResponse } from '@/types'
import { getAccessToken, setAccessToken } from '@/utils/token'

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1'

/**
 * 业务 API 客户端
 *
 * - 自动注入 access_token
 * - 统一响应包装解包（返回 ApiResponse<T>）
 * - 自动 Token 刷新：收到 401 + code=20002 时自动调用 /auth/refresh
 * - 并发请求保护：刷新期间排队的请求等待新 Token 后重试
 */
const apiClient: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true, // 允许携带 Cookie（后端 httpOnly refresh_token）
})

/* ============================================================
 * 请求拦截器：注入 access_token
 * ============================================================ */
apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = getAccessToken()
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

/* ============================================================
 * Token 刷新状态管理
 * ============================================================ */
let isRefreshing = false
let refreshSubscribers: Array<(token: string) => void> = []

function subscribeTokenRefresh(callback: (token: string) => void): void {
  refreshSubscribers.push(callback)
}

function onTokenRefreshed(newToken: string): void {
  refreshSubscribers.forEach((callback) => callback(newToken))
  refreshSubscribers = []
}

/* 未授权处理器（由 main.ts 注入，避免循环依赖 store/router） */
let unauthorizedHandler: (() => void) | null = null

export function setUnauthorizedHandler(handler: () => void): void {
  unauthorizedHandler = handler
}

/* 刷新 Token 专用客户端（不触发 apiClient 拦截器，防止循环） */
const refreshClient = axios.create({
  baseURL: BASE_URL,
  timeout: 30000,
  withCredentials: true,
})

interface RefreshResponse {
  accessToken: string
  expiresIn: number
}

/* ============================================================
 * 响应拦截器：统一错误处理 + 自动 Token 刷新
 * ============================================================ */
apiClient.interceptors.response.use(
  (response: AxiosResponse<ApiResponse<unknown>>) => {
    const { data } = response
    if (data.code !== 200 && data.code !== 201 && data.code !== 202) {
      const error = new Error(data.message || '请求失败')
      ;(error as Error & { code?: number }).code = data.code
      return Promise.reject(error)
    }
    return response
  },
  async (error) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean }
    const status = error.response?.status
    const code = error.response?.data?.code as number | undefined
    const message = error.response?.data?.message || error.message || '网络异常'

    // Token 过期（20002）：自动刷新并重试原请求
    if (status === 401 && code === 20002 && originalRequest && !originalRequest._retry) {
      if (isRefreshing) {
        return new Promise((resolve) => {
          subscribeTokenRefresh((newToken: string) => {
            originalRequest.headers.Authorization = `Bearer ${newToken}`
            resolve(apiClient(originalRequest))
          })
        })
      }

      isRefreshing = true
      originalRequest._retry = true

      try {
        const res = await refreshClient.post<ApiResponse<RefreshResponse>>('/auth/refresh', {})
        if (res.data.code !== 200 && res.data.code !== 201) {
          throw new Error(res.data.message || '刷新 Token 失败')
        }
        const newAccessToken = res.data.data.accessToken
        setAccessToken(newAccessToken)
        onTokenRefreshed(newAccessToken)
        originalRequest.headers.Authorization = `Bearer ${newAccessToken}`
        return apiClient(originalRequest)
      } catch {
        if (unauthorizedHandler) unauthorizedHandler()
        return Promise.reject(new Error('登录已过期，请重新登录'))
      } finally {
        isRefreshing = false
      }
    }

    // 其他 401（20001 Token 无效、20003 refresh_token 无效等）：跳转登录
    if (status === 401 && !originalRequest?._retry) {
      if (unauthorizedHandler) unauthorizedHandler()
    }

    const apiError = new Error(message)
    ;(apiError as Error & { code?: number }).code = code
    return Promise.reject(apiError)
  },
)

export default apiClient
