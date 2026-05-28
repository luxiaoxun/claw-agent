<template>
  <div class="chat-container">
    <!-- 欢迎状态（无会话时） -->
    <div v-if="!sessionId && messages.length === 0" class="welcome-container">
      <div class="welcome-content">
        <div class="welcome-icon">
          <el-icon :size="32"><MagicStick /></el-icon>
        </div>
        <h2 class="welcome-title">欢迎使用 Soma 智能体</h2>
        <p class="welcome-desc">我可以帮助你完成各种任务，请开始对话吧</p>

        <div class="welcome-input-wrapper">
          <el-input
            v-model="inputMessage"
            type="textarea"
            placeholder="输入消息... (Enter 发送, Shift+Enter 换行)"
            :rows="4"
            :autosize="{ minRows: 4, maxRows: 8 }"
            resize="none"
            @keydown.enter.exact.prevent="sendMessage"
            @keydown.enter.shift="handleShiftEnter"
          />
          <div class="welcome-input-actions">
            <el-button circle @click="openFileSelector" title="上传文件" size="small">
              <el-icon><Upload /></el-icon>
            </el-button>
            <el-button
              circle
              type="primary"
              :disabled="!inputMessage.trim()"
              @click="sendMessage"
              title="发送"
              size="small"
            >
              <el-icon><Promotion /></el-icon>
            </el-button>
          </div>
        </div>
      </div>
    </div>

    <!-- 聊天状态（有会话时） -->
    <template v-else>
      <!-- 消息输出区域 -->
      <el-card class="output" ref="outputRef" shadow="hover">
        <div
          v-if="dragActive"
          class="drag-overlay"
          @dragenter="handleDragEnter"
          @dragleave="handleDragLeave"
          @dragover="handleDragOver"
          @drop="handleDrop"
        >
          <div class="drag-content">
            <el-icon :size="32"><Upload /></el-icon>
            <span style="margin-top: 8px;">释放文件以上传</span>
          </div>
        </div>

        <div v-if="loadingHistory" class="loading-history">
          <el-icon class="is-loading"><Loading /></el-icon>
          加载历史消息...
        </div>

        <div
            v-for="(msg, index) in messages"
            :key="index"
            :class="msg.className"
            v-html="msg.html"
        ></div>
      </el-card>

      <!-- 输入区域 -->
      <div class="input-area">
        <div class="input-wrapper">
          <el-input
            v-model="inputMessage"
            type="textarea"
            placeholder="输入消息... (Enter 发送, Shift+Enter 换行)"
            :rows="4"
            :autosize="{ minRows: 4, maxRows: 8 }"
            resize="none"
            @keydown.enter.exact.prevent="sendMessage"
            @keydown.enter.shift="handleShiftEnter"
          />
          <div class="input-actions">
            <el-button circle @click="openFileSelector" title="上传文件" size="small">
              <el-icon><Upload /></el-icon>
            </el-button>
            <el-button
              circle
              type="primary"
              :disabled="!inputMessage.trim()"
              @click="sendMessage"
              title="发送"
              size="small"
            >
              <el-icon><Promotion /></el-icon>
            </el-button>
          </div>
        </div>
      </div>
    </template>

    <!-- 隐藏的文件输入 -->
    <input
        type="file"
        ref="fileInput"
        style="display: none"
        @change="handleFileSelect"
    />

    <!-- 状态栏 -->
    <div :class="['status', statusClass]">
      <el-tag :type="statusTagType" size="small">{{ statusText }}</el-tag>
      <span v-if="currentSessionId" style="margin-left: 10px; color: #909399; font-size: 12px;">
        会话: {{ currentSessionId.substring(0, 8) }}...
      </span>
      <span v-if="dragActive" style="margin-left: 10px; color: #2196f3; font-size: 12px;">
        拖拽文件到此处上传
      </span>
    </div>
  </div>
</template>

<script setup>
import {ref, computed, onMounted, onUnmounted, nextTick, watch} from 'vue'
import { ElIcon, ElTag } from 'element-plus'
import { Upload, Loading, MagicStick, Promotion } from '@element-plus/icons-vue'
import { marked } from 'marked'
import { API_BASE_URL, WS_BASE_URL, sessionApi } from '../utils/api'

// 配置 marked 选项
marked.setOptions({
  breaks: true,      // 换行转换为 <br>
  gfm: true          // GitHub 风格 markdown
})

const props = defineProps({
  sessionId: {
    type: String,
    default: null
  }
})

const emit = defineEmits(['session-created', 'refresh-sessions'])

const ws = ref(null)
const sessionId = ref(props.sessionId)
const messages = ref([])
const inputMessage = ref('')
const status = ref('idle')
const outputRef = ref(null)
const reconnectAttempts = ref(0)
const currentResponseIndex = ref(-1)
const currentResponseContent = ref('')
const loadingHistory = ref(false)

const currentSessionId = computed(() => sessionId.value)

const statusText = computed(() => {
  switch (status.value) {
    case 'idle':
      return '就绪'
    case 'connected':
      return '已连接'
    case 'processing':
      return '处理中...'
    case 'disconnected':
      return '已断开'
    default:
      return '未知'
  }
})

const statusClass = computed(() => status.value)

const statusTagType = computed(() => {
  switch (status.value) {
    case 'connected': return 'success'
    case 'processing': return 'warning'
    case 'disconnected': return 'danger'
    default: return 'info'
  }
})

const escapeHtml = (text) => {
  const div = document.createElement('div')
  div.textContent = text
  return div.innerHTML
}

// 检测并格式化内容中的JSON
const formatJsonInContent = (content) => {
  // 尝试从内容中提取并格式化 JSON
  // 支持对象 { ... } 和数组 [ ... ]
  try {
    // 移除内容中的 \n 换行符，便于 JSON 检测
    const normalizedContent = content.replace(/\\n/g, '\n').replace(/\n/g, ' ')

    // 先尝试直接解析整个内容是否为 JSON
    const trimmed = normalizedContent.trim()
    if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
      try {
        const parsed = JSON.parse(normalizedContent)
        return '```json\n' + JSON.stringify(parsed, null, 2) + '\n```'
      } catch (e) {
        // 不是完整 JSON，继续检测内部片段
      }
    }

    // 检测内部的 JSON 片段
    // 匹配 { ... } 或 [ ... ]，支持嵌套
    const results = []
    let i = 0

    while (i < normalizedContent.length) {
      const ch = normalizedContent[i]
      if (ch === '{') {
        // 尝试匹配对象
        let depth = 0
        let end = -1
        for (let j = i; j < normalizedContent.length; j++) {
          if (normalizedContent[j] === '{') depth++
          else if (normalizedContent[j] === '}') {
            depth--
            if (depth === 0) {
              end = j + 1
              break
            }
          }
        }
        if (end !== -1) {
          const jsonStr = normalizedContent.slice(i, end)
          try {
            const parsed = JSON.parse(jsonStr)
            results.push({
              start: i,
              end: end,
              formatted: '```json\n' + JSON.stringify(parsed, null, 2) + '\n```'
            })
            i = end
            continue
          } catch (e) {
            // 不是有效 JSON
          }
        }
      } else if (ch === '[') {
        // 尝试匹配数组
        let depth = 0
        let end = -1
        for (let j = i; j < normalizedContent.length; j++) {
          if (normalizedContent[j] === '[') depth++
          else if (normalizedContent[j] === ']') {
            depth--
            if (depth === 0) {
              end = j + 1
              break
            }
          }
        }
        if (end !== -1) {
          const jsonStr = normalizedContent.slice(i, end)
          try {
            const parsed = JSON.parse(jsonStr)
            results.push({
              start: i,
              end: end,
              formatted: '```json\n' + JSON.stringify(parsed, null, 2) + '\n```'
            })
            i = end
            continue
          } catch (e) {
            // 不是有效 JSON
          }
        }
      }
      i++
    }

    // 如果没有找到有效 JSON，返回原内容
    if (results.length === 0) {
      return content
    }

    // 替换内容中所有检测到的 JSON
    let formattedContent = ''
    let offset = 0
    for (const item of results) {
      if (item.start >= offset) {
        formattedContent += normalizedContent.slice(offset, item.start)
        formattedContent += item.formatted
        offset = item.end
      }
    }
    formattedContent += normalizedContent.slice(offset)

    return formattedContent
  } catch (e) {
    return content
  }
}

const renderMarkdown = (content) => {
  try {
    // 先格式化 JSON
    const formattedContent = formatJsonInContent(content)
    return marked.parse(formattedContent)
  } catch (e) {
    console.error('Markdown 解析失败:', e)
    return escapeHtml(content)
  }
}

const scrollToBottom = async () => {
  await nextTick()
  if (outputRef.value) {
    const el = outputRef.value.$el
    if (el) {
      // el-card 的内容在 .el-card__body 中，找到真正的滚动容器
      const cardBody = el.querySelector('.el-card__body') || el
      cardBody.scrollTop = cardBody.scrollHeight
    }
  }
}

const scrollToBottomDelayed = async () => {
  await nextTick()
  if (outputRef.value) {
    const el = outputRef.value.$el
    if (el) {
      const cardBody = el.querySelector('.el-card__body') || el
      setTimeout(() => {
        cardBody.scrollTop = cardBody.scrollHeight
      }, 50)
    }
  }
}

const addMessage = (sender, content, className, isIndented = false, isMarkdown = false, timestamp = null) => {
  const timeStr = timestamp
    ? new Date(timestamp).toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' })
    : new Date().toLocaleTimeString()
  const prefix = isIndented ? '&nbsp;&nbsp;&nbsp;&nbsp;' : ''

  // 如果需要渲染markdown，先解析内容
  const displayContent = isMarkdown ? renderMarkdown(content) : escapeHtml(content)

  // 根据消息类型选择不同的容器样式
  let containerClass = 'message-item'
  let html = ''

  if (className === 'system') {
    // 系统消息：单行显示，sender和content合并
    html = `<div class="${containerClass} system-message">
      <span class="system-label">系统</span>
      <span class="system-content">${displayContent}</span>
    </div>`
  } else {
    if (className === 'user') {
      containerClass += ' user-message'
    } else if (className === 'assistant') {
      containerClass += ' assistant-message'
    }
    html = `<div class="${containerClass}">
      <div class="message-header"><span class="sender">${escapeHtml(sender)}</span><span class="timestamp">${timeStr}</span></div>
      <div class="message-content">${prefix}${displayContent}</div>
    </div>`
  }

  messages.value.push({
    className,
    html
  })
  scrollToBottom()
}

const createResponseContainer = () => {
  currentResponseContent.value = ''
  const timeStr = new Date().toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' })

  const html = `<div class="message-item assistant-message">
    <div class="message-header"><span class="sender">助手</span><span class="timestamp">${timeStr}</span></div>
    <div class="message-content assistant-content"></div>
  </div>`

  messages.value.push({
    className: 'assistant',
    html
  })
  currentResponseIndex.value = messages.value.length - 1
  scrollToBottom()
}

const appendToLastMessage = (content) => {
  currentResponseContent.value += content
  if (currentResponseIndex.value !== -1) {
    // 流式输出时先不渲染 markdown，只转义 HTML，避免 JSON 检测不完整的问题
    messages.value[currentResponseIndex.value].html = `<div class="message-item assistant-message">
      <div class="message-header"><span class="sender">助手</span></div>
      <div class="message-content assistant-content">${escapeHtml(currentResponseContent.value)}</div>
    </div>`
    scrollToBottom()
  } else {
    createResponseContainer()
    appendToLastMessage(content)
  }
}

// 消息完成后，渲染完整的 markdown（包含 JSON 格式化）
const finalizeMessage = () => {
  if (currentResponseIndex.value !== -1 && currentResponseContent.value) {
    messages.value[currentResponseIndex.value].html = `<div class="message-item assistant-message">
      <div class="message-header"><span class="sender">助手</span></div>
      <div class="message-content assistant-content">${renderMarkdown(currentResponseContent.value)}</div>
    </div>`
  }
}

const closeWebSocket = () => {
  if (ws.value && ws.value.readyState === WebSocket.OPEN) {
    console.log('关闭现有WebSocket连接...')
    ws.value.close()
  }
}

const closeSession = () => {
  console.log('关闭当前会话...')
  closeWebSocket()
  sessionId.value = null
  messages.value = []
  inputMessage.value = ''
  status.value = 'idle'
  currentResponseIndex.value = -1
  currentResponseContent.value = ''
}

const clearCurrentSession = () => {
  if (confirm('确定要清空当前会话消息吗？')) {
    messages.value = []
    inputMessage.value = ''
  }
}

const loadSessionHistory = async (sid) => {
  if (!sid) {
    console.log('loadSessionHistory: sid is empty, skip')
    return
  }

  console.log('loadSessionHistory: 开始加载会话历史', sid)
  loadingHistory.value = true
  messages.value = []
  addMessage('系统', `加载会话历史: ${sid.substring(0, 8)}...`, 'system')

  try {
    const data = await sessionApi.getMessages(sid)
    console.log('loadSessionHistory: 响应数据', data)

    if (data && data.rounds !== undefined) {
      const rounds = data.rounds || []
      console.log('loadSessionHistory: 获取到轮次数量', rounds.length)

      if (rounds.length === 0) {
        addMessage('系统', '暂无历史消息', 'system')
      } else {
        addMessage('系统', `加载了 ${rounds.length} 条历史消息`, 'system')

        for (const round of rounds) {
          console.log('loadSessionHistory: 加载轮次', round.round_number, round.user_message.substring(0, 50))
          addMessage('用户', round.user_message, 'user', false, false, round.create_time)
          addMessage('助手', round.ai_message, 'assistant', false, true, round.create_time)
        }
        // 加载完成后滚动到底部
        scrollToBottomDelayed()
      }
    } else {
      addMessage('系统', '暂无历史消息', 'system')
    }
    // 加载成功后自动建立 WebSocket 连接
    connect()
  } catch (e) {
    console.error('加载历史消息失败:', e)
    addMessage('系统', `加载历史失败: ${e.message || e}`, 'system')
    // 也尝试建立连接（新会话没有历史也能聊）
    connect()
  } finally {
    loadingHistory.value = false
  }
}

const connect = () => {
  console.log('connect called, current ws state:', ws.value?.readyState)
  if (ws.value && ws.value.readyState === WebSocket.OPEN) {
    console.log('已有连接，不需要重复连接')
    return  // 已有连接，不需要重复连接
  }

  status.value = 'connecting'
  const wsUrl = WS_BASE_URL()
  console.log('尝试连接 WebSocket:', wsUrl)

  try {
    ws.value = new WebSocket(wsUrl)

    ws.value.onopen = () => {
      console.log('WebSocket 连接已建立')
      status.value = 'connected'
      addMessage('系统', 'WebSocket 连接已建立', 'system')
      reconnectAttempts.value = 0
    }

    ws.value.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)

        switch (data.type) {
          case 'connection':
            addMessage('系统', data.message || '连接成功', 'system')
            break

          case 'session':
            if (data.session_id) {
              sessionId.value = data.session_id
              addMessage('系统', `会话ID: ${data.session_id.substring(0, 8)}...`, 'system')
              emit('session-created', data.session_id)
            }
            break

          case 'chunk':
            appendToLastMessage(data.content)
            break

          case 'tool_call':
            // 工具调用：紧凑显示
            if (data.tool_args && Object.keys(data.tool_args).length > 0) {
              const argsStr = JSON.stringify(data.tool_args)
              const preview = argsStr.length > 100 ? argsStr.substring(0, 100) + '...' : argsStr
              addMessage('工具调用', `${data.tool_name}(${preview})`, 'tool-call')
            } else {
              addMessage('工具调用', `${data.tool_name}()`, 'tool-call')
            }
            break

          case 'tool_result':
            // 工具结果：紧凑显示
            const resultPreview = typeof data.result === 'string'
                ? data.result.substring(0, 150)
                : JSON.stringify(data.result).substring(0, 150)
            const statusIcon = data.status === 'error' ? '❌' : '✅'
            addMessage('工具结果', `${statusIcon} ${resultPreview}${resultPreview.length >= 150 ? '...' : ''}`, 'tool-result')
            break

          case 'complete':
            // 消息完成时，渲染完整的 markdown（包含 JSON 格式化）
            finalizeMessage()
            addMessage('完成', '消息处理完成', 'system')
            status.value = 'connected'
            currentResponseIndex.value = -1
            currentResponseContent.value = ''
            // 刷新会话列表
            emit('refresh-sessions')
            break

          case 'file_received':
            handleFileReceived(data)
            break

          case 'error':
            addMessage('错误', data.error, 'error')
            status.value = 'disconnected'
            currentResponseIndex.value = -1
            currentResponseContent.value = ''
            break

          default:
            console.log('未知消息类型:', data)
        }
      } catch (e) {
        console.error('解析消息失败:', e, event.data)
        addMessage('错误', `解析消息失败: ${e.message}`, 'error')
      }
    }

    ws.value.onclose = (event) => {
      console.log('WebSocket 连接已关闭', event.code, event.reason)
      status.value = 'disconnected'
      addMessage('系统', 'WebSocket 连接已断开', 'system')

      // 如果流式输出中断但还有内容，需要渲染已完成的消息
      if (currentResponseIndex.value !== -1 && currentResponseContent.value) {
        finalizeMessage()
        currentResponseIndex.value = -1
        currentResponseContent.value = ''
      }

      if (reconnectAttempts.value < maxReconnectAttempts && !window.isManualClose) {
        reconnectAttempts.value++
        const delay = 5000
        addMessage('系统', `${delay / 1000}秒后尝试重连... (${reconnectAttempts.value}/${maxReconnectAttempts})`, 'system')
        setTimeout(() => {
          if (ws.value.readyState === WebSocket.CLOSED) {
            addMessage('系统', '尝试重新连接...', 'system')
            connect()
          }
        }, delay)
      } else if (reconnectAttempts.value >= maxReconnectAttempts) {
        addMessage('错误', '重连失败，请刷新页面手动重连', 'error')
      }
    }

    ws.value.onerror = (error) => {
      console.error('WebSocket 错误:', error)
      status.value = 'disconnected'
      addMessage('错误', 'WebSocket 连接错误', 'error')
    }

  } catch (error) {
    console.error('创建 WebSocket 连接失败:', error)
    addMessage('错误', `创建连接失败: ${error.message}`, 'error')
    status.value = 'disconnected'
  }
}

const sendMessage = () => {
  const message = inputMessage.value.trim()

  if (!message) {
    return
  }

  // 如果没有会话ID，先创建会话
  if (!sessionId.value) {
    createSessionAndSend(message)
    return
  }

  // 如果未连接，先建立连接
  if (!ws.value || ws.value.readyState !== WebSocket.OPEN) {
    addMessage('系统', '正在建立连接...', 'system')
    connect()
    // 等待连接建立后再发送（通过onopen回调）
    ws.value?.addEventListener('open', () => {
      setTimeout(() => sendMessage(), 100)
    }, { once: true })
    return
  }

  doSendMessage(message)
}

const createSessionAndSend = async (message) => {
  try {
    const data = await sessionApi.create()
    if (data && data.session_id) {
      sessionId.value = data.session_id
      emit('session-created', data.session_id)
      // 等待会话创建后再发送
      await nextTick()
      connect()
      ws.value?.addEventListener('open', () => {
        setTimeout(() => {
          doSendMessage(message)
        }, 100)
      }, { once: true })
    } else {
      addMessage('错误', '创建会话失败', 'error')
    }
  } catch (e) {
    console.error('创建会话失败:', e)
    addMessage('错误', `创建会话失败: ${e.message}`, 'error')
  }
}

const doSendMessage = (message) => {
  const messageData = {
    message: message,
    session_id: sessionId.value
  }

  console.log('发送消息:', messageData)
  ws.value.send(JSON.stringify(messageData))

  addMessage('用户', message, 'user')
  inputMessage.value = ''
  createResponseContainer()
  status.value = 'processing'
}

const handleShiftEnter = (e) => {
  // Shift+Enter inserts newline - default behavior is prevented by not handling it
}

const dragActive = ref(false)
const fileInput = ref(null)
const maxReconnectAttempts = 5

const sendFile = (file) => {
  // 如果未连接，先建立连接
  if (!ws.value || ws.value.readyState !== WebSocket.OPEN) {
    addMessage('系统', '正在建立连接...', 'system')
    connect()
    ws.value?.addEventListener('open', () => {
      setTimeout(() => sendFile(file), 100)
    }, { once: true })
    return false
  }

  const reader = new FileReader()

  reader.onload = () => {
    const metadata = {
      filename: file.name,
      filetype: file.type,
      size: file.size,
      timestamp: new Date().toISOString()
    }

    const metadataStr = JSON.stringify(metadata)
    const metadataBytes = new TextEncoder().encode(metadataStr)
    const metadataLength = metadataBytes.length

    const buffer = new ArrayBuffer(4 + metadataLength + file.size)
    const view = new DataView(buffer)

    view.setUint32(0, metadataLength, false)

    const metadataBuffer = new Uint8Array(buffer, 4, metadataLength)
    metadataBuffer.set(metadataBytes)

    const fileBuffer = new Uint8Array(buffer, 4 + metadataLength, file.size)
    fileBuffer.set(new Uint8Array(reader.result))

    ws.value.send(buffer)

    const formattedSize = formatFileSize(file.size)
    addMessage('用户', `📎 上传文件: ${file.name} (${formattedSize})`, 'user')
    addMessage('系统', `文件上传中...`, 'system')
  }

  reader.onerror = () => {
    addMessage('错误', `文件读取失败: ${file.name}`, 'error')
  }

  reader.readAsArrayBuffer(file)
  return true
}

const handleDragEnter = (e) => {
  e.preventDefault()
  dragActive.value = true
}

const handleDragLeave = (e) => {
  e.preventDefault()
  dragActive.value = false
}

const handleDragOver = (e) => {
  e.preventDefault()
}

const handleDrop = (e) => {
  e.preventDefault()
  dragActive.value = false

  const files = e.dataTransfer.files
  if (files.length > 0) {
    const file = files[0]
    if (file.size > 100 * 1024 * 1024) {
      addMessage('错误', `文件太大: ${file.name} (超过100MB限制)`, 'error')
      return
    }
    sendFile(file)
  }
}

const openFileSelector = () => {
  fileInput.value.click()
}

const handleFileSelect = (e) => {
  const files = e.target.files
  if (files.length > 0) {
    const file = files[0]
    if (file.size > 100 * 1024 * 1024) {
      addMessage('错误', `文件太大: ${file.name} (超过100MB限制)`, 'error')
      return
    }
    sendFile(file)
  }
  fileInput.value.value = ''
}

const formatFileSize = (bytes) => {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

const handleFileReceived = (data) => {
  const fileInfo = data.file_info
  const formattedSize = formatFileSize(fileInfo.size)
  addMessage('系统', `✅ 文件上传成功: ${fileInfo.name} (${formattedSize})`, 'system')
  addMessage('系统', `📁 保存为: ${fileInfo.saved_name}`, 'system', true)
  if (fileInfo.url) {
    addMessage('系统', `🔗 访问路径: ${fileInfo.url}`, 'system', true)
  }
  console.log('文件上传成功详情:', fileInfo)
}

// Watch for sessionId prop changes
watch(() => props.sessionId, (newId, oldId) => {
  console.log('watch sessionId: old=', oldId, 'new=', newId)
  if (newId) {
    sessionId.value = newId
    loadSessionHistory(newId)
  }
}, { immediate: true })

defineExpose({ closeSession, connect })

onMounted(() => {
  console.log('页面加载，初始化聊天...')
  // 不再自动连接，等待用户发送消息时再连接

  window.addEventListener('beforeunload', () => {
    window.isManualClose = true
    if (ws.value && ws.value.readyState === WebSocket.OPEN) {
      ws.value.close()
    }
  })
})

onUnmounted(() => {
  if (ws.value && ws.value.readyState === WebSocket.OPEN) {
    ws.value.close()
  }
})
</script>

<style scoped>
.chat-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  width: 100%;
  padding: 16px 20px;
}

/* ===== 欢迎状态样式 ===== */
.welcome-container {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 0;
  padding: 20px 40px;
  box-sizing: border-box;
}

.welcome-content {
  text-align: center;
  width: 100%;
  max-width: 900px;
}

.welcome-icon {
  color: #409eff;
  margin-bottom: 16px;
}

.welcome-title {
  font-size: 24px;
  font-weight: 600;
  color: #303133;
  margin: 0 0 12px 0;
}

.welcome-desc {
  font-size: 14px;
  color: #909399;
  margin: 0 0 32px 0;
}

.welcome-input-wrapper {
  position: relative;
  width: 100%;
  max-width: 100%;
  margin: 0 auto;
  text-align: left;
  min-width: 600px;
  max-width: 900px;
}

.welcome-input-wrapper :deep(.el-textarea) {
  width: 100%;
}

.welcome-input-wrapper :deep(.el-textarea__inner) {
  border-radius: 8px;
  width: 100%;
  box-sizing: border-box;
  padding-right: 80px;
}

.welcome-input-actions {
  position: absolute;
  right: 8px;
  bottom: 6px;
  display: flex;
  gap: 4px;
  align-items: center;
}

/* ===== 聊天输入框样式 ===== */
.input-area {
  margin-top: 16px;
}

.input-wrapper {
  position: relative;
  border-radius: 8px;
}

.input-wrapper :deep(.el-textarea__inner) {
  padding-right: 80px;
}

.input-actions {
  position: absolute;
  right: 8px;
  bottom: 6px;
  display: flex;
  gap: 4px;
  align-items: center;
}

.output {
  position: relative;
  flex: 1;
  margin-top: 16px;
  border-radius: 8px;
  padding: 16px;
  min-height: 300px;
  overflow-y: auto;
  background-color: #f5f5f5;
  transition: all 0.3s ease;
}

/* 消息容器 */
:deep(.message-item) {
  margin-bottom: 16px;
  padding: 12px 16px;
  border-radius: 12px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

/* 拖拽上传 */
.drag-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(33, 150, 243, 0.1);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10;
  border-radius: 8px;
}

.drag-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 20px 40px;
  border-radius: 10px;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
  font-size: 16px;
  color: #2196f3;
}

/* 用户消息 - 蓝色背景，右对齐 */
:deep(.user-message) {
  background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
  margin-left: 60px;
  border-bottom-right-radius: 4px;
}

/* 助手消息 - 白色背景，左对齐 */
:deep(.assistant-message) {
  background: linear-gradient(135deg, #ffffff 0%, #fafafa 100%);
  margin-right: 60px;
  border-bottom-left-radius: 4px;
}

/* 错误消息 - 浅红色背景 */
:deep(.error) {
  background: linear-gradient(135deg, #ffebee 0%, #ffcdd2 100%);
  color: #c62828;
  border-left: 3px solid #c62828;
}

/* 系统消息 - 单行block显示，左对齐 */
:deep(.system-message) {
  display: inline-flex;
  align-items: center;
  justify-content: flex-start;
  gap: 8px;
  background: transparent;
  padding: 4px 12px;
  margin: 4px 0;
  border-radius: 16px;
  width: 100%;
}

:deep(.system-label) {
  font-size: 11px;
  font-weight: 600;
  color: #999;
  background: #eee;
  padding: 2px 8px;
  border-radius: 10px;
}

:deep(.system-content) {
  font-size: 12px;
  color: #888;
  font-style: italic;
}

/* 消息头部：发送者和时间 */
:deep(.message-header) {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  padding-bottom: 6px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
}

:deep(.message-header .sender) {
  font-weight: 600;
  font-size: 13px;
  color: #333;
}

:deep(.message-header .timestamp) {
  font-size: 11px;
  color: #999;
}

/* 消息内容 */
:deep(.message-content) {
  line-height: 1.6;
  font-size: 14px;
  color: #333;
  word-wrap: break-word;
}

/* 助手消息内容样式 */
:deep(.assistant-content) {
  color: #1a1a1a;
}

/* 工具调用样式 - 紧凑 */
:deep(.tool-call) {
  background: #e8f4fd;
  color: #0066cc;
  font-size: 12px;
  padding: 2px 6px;
  border-radius: 3px;
  border-left: 2px solid #2196f3;
  margin: 2px 0;
}

/* 工具结果样式 - 紧凑 */
:deep(.tool-result) {
  background: #f0f9f0;
  color: #009900;
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 3px;
  border-left: 2px solid #4caf50;
  margin: 2px 0;
}

/* Markdown 代码块样式 */
:deep(.message-content pre) {
  background: #f5f5f5;
  color: #333;
  padding: 12px 16px;
  border-radius: 6px;
  overflow-x: auto;
  margin: 8px 0;
  border: 1px solid #e0e0e0;
}

:deep(.message-content code) {
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 13px;
}

:deep(.message-content pre code) {
  background: transparent;
  color: inherit;
}

/* JSON 代码块特殊样式 - 浅蓝背景 */
:deep(.message-content pre.language-json) {
  background: linear-gradient(135deg, #e3f2fd 0%, #e1f5fe 100%);
  border-left: 4px solid #2196f3;
  border-radius: 8px;
}

/* 普通代码块样式 */
:deep(.message-content pre:not(.language-json)) {
  background: #f8f8f8;
  border: 1px solid #e0e0e0;
}

:deep(.message-content code:not(pre code)) {
  background: #f0f0f0;
  color: #c62828;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 13px;
}

/* Markdown 列表和加粗斜体 */
:deep(.message-content ul),
:deep(.message-content ol) {
  margin: 8px 0;
  padding-left: 20px;
}

:deep(.message-content li) {
  margin: 4px 0;
}

:deep(.message-content strong) {
  color: #1565c0;
}

:deep(.message-content em) {
  color: #666;
}

/* 引用样式 */
:deep(.message-content blockquote) {
  border-left: 3px solid #2196f3;
  margin: 8px 0;
  padding: 8px 12px;
  background: #f5f5f5;
  color: #555;
}

/* 状态栏 */
.status {
  margin-top: 12px;
  font-size: 12px;
  color: #909399;
  display: flex;
  align-items: center;
  gap: 8px;
}

.loading-history {
  text-align: center;
  padding: 20px;
  color: #909399;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}
</style>