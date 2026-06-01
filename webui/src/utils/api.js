import { ElMessage } from 'element-plus'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api'
const AUTH_MODE = import.meta.env.VITE_AUTH_MODE || 'shared'
const API_KEY = import.meta.env.VITE_API_KEY || ''

function getAuthHeaders() {
  if (AUTH_MODE === 'standalone') {
    // Standalone 模式: 使用 API Key
    if (API_KEY) {
      return { 'X-API-Key': API_KEY }
    }
  } else {
    // Shared 模式: 从 localStorage 获取用户信息
    const userId = localStorage.getItem('shared_user_id')
    if (userId) {
      return { 'X-User-Id': userId }
    }
    // Shared 模式: 开发环境下使用默认用户
    if (import.meta.env.DEV) {
      return { 'X-User-Id': 'admin' }
    }
  }
  return {}
}

async function request(url, options = {}) {
  try {
    const headers = { ...options.headers, ...getAuthHeaders() }
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

// WebSocket URL builder
export const WS_BASE_URL = () => {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.host

  // 获取认证信息
  let userId = 'admin'
  if (AUTH_MODE === 'standalone' && API_KEY) {
    // Standalone 模式暂不支持 WebSocket
  } else {
    // Shared 模式
    const storedUserId = localStorage.getItem('shared_user_id')
    if (storedUserId) {
      userId = storedUserId
    } else if (import.meta.env.DEV) {
      userId = 'admin'
    }
  }

  // 开发模式下 VITE_API_BASE_URL 配置了完整后端地址 (http://127.0.0.1:5000/api)
  // WebSocket 需要直连后端，不走 Vite 代理
  if (API_BASE_URL.startsWith('http')) {
    // 完整 URL 模式：提取 host 并拼接 ws 路径
    const url = new URL(API_BASE_URL)
    return `${protocol}//${url.host}/api/chat/ws/message?user_id=${encodeURIComponent(userId)}`
  }
  // 生产模式或相对路径模式：使用当前主机
  return `${protocol}//${host}/api/chat/ws/message?user_id=${encodeURIComponent(userId)}`
}

// Session APIs
export const sessionApi = {
  list: (limit = 50, offset = 0) => api.get(`/session/?limit=${limit}&offset=${offset}`),

  create: () => api.post('/session/create', {}),

  rename: (sessionId, title) => api.put(`/session/${sessionId}`, { title }),

  delete: (sessionId) => api.delete(`/session/${sessionId}`),

  getMessages: (sessionId) => api.get(`/session/${sessionId}/messages`)
}

// Workspace APIs
export const workspaceApi = {
  tree: () => api.get('/workspace/tree'),

  list: (path) => api.get(`/workspace/list?path=${encodeURIComponent(path)}`),

  read: (path) => api.get(`/workspace/read?path=${encodeURIComponent(path)}`)
}

// Skill APIs
export const skillApi = {
  list: () => api.get('/skill/list'),

  get: (name) => api.get(`/skill/${name}`),

  preview: (formData) => api.post('/skill/preview', formData, true),

  import: (formData) => api.post('/skill/import', formData, true)
}

// RAG APIs
export const ragApi = {
  listCollections: () => api.get('/rag/collection/list'),

  createCollection: (data) => api.post('/rag/collection/create', data),

  updateCollection: (id, data) => api.post(`/rag/collection/${id}/update`, data),

  deleteCollection: (id) => api.post(`/rag/collection/${id}/delete`),

  listDocuments: (collectionId) => api.get(`/rag/collection/${collectionId}/documents`),

  uploadDocument: (collectionId, file) => {
    const formData = new FormData()
    formData.append('file', file)
    const headers = { ...getAuthHeaders() }
    return fetch(`${API_BASE_URL}/rag/collection/${collectionId}/document/upload`, {
      method: 'POST',
      headers,
      body: formData
    }).then(res => res.json()).then(data => {
      if (data.code !== "200") {
        ElMessage.error(data.message || '上传失败')
        return null
      }
      return data.data  // { task_id: string }
    })
  },

  getTaskStatus: (taskId) => api.get(`/rag/task/${taskId}/status`),

  deleteDocument: (collectionId, docId) => api.post(`/rag/collection/${collectionId}/document/${docId}/delete`),

  search: (data) => api.post('/rag/search', data)
}