import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authService } from '@/api/auth'
import { setAccessToken, clearAccessToken } from '@/utils/token'
import type { UserInfo, LoginRequest } from '@/types'

export const useAuthStore = defineStore('auth', () => {
  const accessToken = ref<string>(localStorage.getItem('access_token') || '')
  const user = ref<UserInfo | null>(null)
  const loading = ref(false)

  const isLoggedIn = computed(() => !!accessToken.value)

  /**
   * 检查当前用户是否拥有指定权限
   * @param perm 权限码，如 project:read
   */
  function hasPermission(perm: string): boolean {
    if (!user.value?.permissions) return false
    return user.value.permissions.includes(perm)
  }

  async function login(credentials: LoginRequest): Promise<void> {
    loading.value = true
    try {
      const result = await authService.login(credentials)
      accessToken.value = result.accessToken
      setAccessToken(result.accessToken)
    } finally {
      loading.value = false
    }
  }

  async function fetchUser(): Promise<void> {
    try {
      const res = await authService.getCurrentUser()
      user.value = res
    } catch {
      user.value = null
    }
  }

  async function refreshToken(): Promise<void> {
    const result = await authService.refreshToken()
    accessToken.value = result.accessToken
    setAccessToken(result.accessToken)
  }

  async function logout(): Promise<void> {
    try {
      await authService.logout()
    } finally {
      clearAuthState()
    }
  }

  function clearAuthState(): void {
    accessToken.value = ''
    user.value = null
    clearAccessToken()
  }

  return {
    accessToken,
    user,
    loading,
    isLoggedIn,
    hasPermission,
    login,
    fetchUser,
    refreshToken,
    logout,
    clearAuthState,
  }
})
