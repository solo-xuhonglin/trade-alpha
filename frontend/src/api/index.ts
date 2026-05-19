import axios, { AxiosError } from 'axios'
import type { ApiErrorResponse } from './types'
import { notifyService } from '@/utils/notify'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

// Response interceptor for unified error handling
api.interceptors.response.use(
  (response) => response,
  (error: AxiosError<ApiErrorResponse>) => {
    let errorMessage = '请求失败，请稍后重试'

    if (error.response) {
      const { data, status } = error.response
      
      if (data?.error?.message) {
        errorMessage = data.error.message
      } else {
        switch (status) {
          case 400:
            errorMessage = '请求参数错误'
            break
          case 401:
            errorMessage = '未授权，请重新登录'
            break
          case 403:
            errorMessage = '无权限访问'
            break
          case 404:
            errorMessage = '资源不存在'
            break
          case 409:
            errorMessage = '资源冲突'
            break
          case 422:
            errorMessage = '数据验证失败'
            break
          case 500:
            errorMessage = '服务器内部错误'
            break
          default:
            errorMessage = `请求失败 (${status})`
        }
      }
    } else if (error.request) {
      errorMessage = '网络连接失败，请检查网络'
    } else {
      errorMessage = error.message || '请求失败'
    }

    // Show error notification
    notifyService.error(errorMessage)
    
    return Promise.reject(error)
  }
)

export default api
