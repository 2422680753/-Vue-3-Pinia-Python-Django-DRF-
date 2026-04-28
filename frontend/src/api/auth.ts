import { request } from './request'

export interface LoginData {
  username: string
  password: string
}

export interface RegisterData {
  username: string
  email: string
  password: string
  re_password: string
  role?: string
  real_name?: string
}

export interface UserInfo {
  id: number
  username: string
  email: string
  role: string
  real_name: string
  avatar: string | null
  phone: string | null
  is_active: boolean
  last_login: string | null
  created_at: string
}

export interface TokenResponse {
  access: string
  refresh: string
}

export const authApi = {
  login(data: LoginData): Promise<TokenResponse> {
    return request.post('/token/', data)
  },

  register(data: RegisterData): Promise<any> {
    return request.post('/users/register/', data)
  },

  refreshToken(refresh: string): Promise<TokenResponse> {
    return request.post('/token/refresh/', { refresh })
  },

  getUserInfo(): Promise<UserInfo> {
    return request.get('/users/me/')
  },

  updateUserInfo(data: Partial<UserInfo>): Promise<UserInfo> {
    return request.put('/users/me/', data)
  },

  changePassword(data: {
    old_password: string
    new_password: string
    re_password: string
  }): Promise<any> {
    return request.post('/users/change-password/', data)
  },

  logout(): Promise<any> {
    return request.post('/users/logout/')
  }
}
