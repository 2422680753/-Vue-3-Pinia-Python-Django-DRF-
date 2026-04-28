import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi, UserInfo, LoginData, RegisterData } from '@/api/auth'
import { jwtDecode } from 'jwt-decode'

interface JwtPayload {
  user_id: number
  username: string
  exp: number
  iat: number
}

export const useUserStore = defineStore('user', () => {
  const userInfo = ref<UserInfo | null>(null)
  const token = ref<string>(localStorage.getItem('access_token') || '')
  const refreshToken = ref<string>(localStorage.getItem('refresh_token') || '')

  const isLoggedIn = computed(() => !!token.value)
  const isAdmin = computed(() => userInfo.value?.role === 'admin')
  const isTeacher = computed(() => userInfo.value?.role === 'teacher')
  const isStudent = computed(() => userInfo.value?.role === 'student')

  async function login(data: LoginData) {
    const response = await authApi.login(data)
    token.value = response.access
    refreshToken.value = response.refresh
    
    localStorage.setItem('access_token', response.access)
    localStorage.setItem('refresh_token', response.refresh)
    
    await getUserInfo()
    return response
  }

  async function register(data: RegisterData) {
    return await authApi.register(data)
  }

  async function getUserInfo() {
    try {
      const info = await authApi.getUserInfo()
      userInfo.value = info
      return info
    } catch (error) {
      logout()
      throw error
    }
  }

  async function updateUserInfo(data: Partial<UserInfo>) {
    const info = await authApi.updateUserInfo(data)
    userInfo.value = info
    return info
  }

  async function changePassword(data: {
    old_password: string
    new_password: string
    re_password: string
  }) {
    return await authApi.changePassword(data)
  }

  function logout() {
    userInfo.value = null
    token.value = ''
    refreshToken.value = ''
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
  }

  async function refreshAccessToken() {
    if (!refreshToken.value) {
      logout()
      return null
    }
    
    try {
      const response = await authApi.refreshToken(refreshToken.value)
      token.value = response.access
      localStorage.setItem('access_token', response.access)
      return response
    } catch (error) {
      logout()
      return null
    }
  }

  function isTokenValid() {
    if (!token.value) return false
    
    try {
      const decoded: JwtPayload = jwtDecode(token.value)
      const now = Date.now() / 1000
      return decoded.exp > now
    } catch {
      return false
    }
  }

  return {
    userInfo,
    token,
    refreshToken,
    isLoggedIn,
    isAdmin,
    isTeacher,
    isStudent,
    login,
    register,
    getUserInfo,
    updateUserInfo,
    changePassword,
    logout,
    refreshAccessToken,
    isTokenValid
  }
})
