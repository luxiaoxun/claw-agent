import { ElMessage } from 'element-plus'

const API_BASE_URL = 'http://127.0.0.1:5000/api'

async function request(url, options = {}) {
  try {
    const headers = options.headers || {}
    const res = await fetch(`${API_BASE_URL}${url}`, {
      ...options,
      headers
    })
    const data = await res.json()

    if (data.code !== "200") {
      ElMessage.error(data.message || '请求失败')
      return null
    }

    return data.data
  } catch (e) {
    console.error('请求失败:', e)
    ElMessage.error('网络请求失败')
    return null
  }
}

function buildBody(body) {
  if (body instanceof FormData) {
    return body
  }
  return JSON.stringify(body)
}

export const api = {
  get: (url) => request(url),

  post: (url, body, isFormData = false) => request(url, {
    method: 'POST',
    body: buildBody(body),
    headers: isFormData ? {} : { 'Content-Type': 'application/json' }
  }),

  put: (url, body) => request(url, {
    method: 'PUT',
    body: JSON.stringify(body),
    headers: { 'Content-Type': 'application/json' }
  }),

  delete: (url) => request(url, { method: 'DELETE' })
}

// Channel APIs
export const channelApi = {
  list: (platform, enabled) => {
    let url = '/channel/list'
    const params = []
    if (platform) params.push(`platform=${platform}`)
    if (enabled !== undefined) params.push(`enabled=${enabled}`)
    if (params.length) url += '?' + params.join('&')
    return api.get(url)
  },

  get: (channelId) => api.get(`/channel/${channelId}`),

  create: (platform, name, config, description, enabled) => api.post('/channel/create', {
    platform, name, config, description, enabled
  }),

  update: (channelId, data) => api.post(`/channel/${channelId}/update`, data),

  delete: (channelId) => api.post(`/channel/${channelId}/delete`),

  enable: (channelId) => api.post(`/channel/${channelId}/enable`),

  disable: (channelId) => api.post(`/channel/${channelId}/disable`),

  restart: (channelId) => api.post(`/channel/${channelId}/restart`),

  getStatus: (channelId) => api.get(`/channel/status/${channelId}`)
}

export { API_BASE_URL }