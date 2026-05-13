import { ElMessage } from 'element-plus'

const API_BASE_URL = 'http://127.0.0.1:5000/api'

async function request(url, options = {}) {
  try {
    const res = await fetch(`${API_BASE_URL}${url}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers
      }
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

export const api = {
  get: (url) => request(url),

  post: (url, body) => request(url, {
    method: 'POST',
    body: JSON.stringify(body)
  }),

  put: (url, body) => request(url, {
    method: 'PUT',
    body: JSON.stringify(body)
  }),

  delete: (url) => request(url, { method: 'DELETE' })
}

export { API_BASE_URL }