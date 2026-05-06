/**
 * Access Token 管理器
 *
 * Tech Spec 约定：refresh_token 由后端通过 httpOnly Cookie 返回，前端不存 localStorage。
 * 本模块仅管理 access_token 的内存缓存 + localStorage 持久化。
 */

let _accessToken: string = localStorage.getItem('access_token') || ''

export function getAccessToken(): string {
  return _accessToken
}

export function setAccessToken(token: string): void {
  _accessToken = token
  localStorage.setItem('access_token', token)
}

export function clearAccessToken(): void {
  _accessToken = ''
  localStorage.removeItem('access_token')
}
