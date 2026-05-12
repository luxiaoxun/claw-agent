<template>
  <div>
    <h2>AI Agent测试</h2>

    <!-- 消息输出区域 -->
    <div
        class="output"
        ref="outputRef"
        @dragenter="handleDragEnter"
        @dragleave="handleDragLeave"
        @dragover="handleDragOver"
        @drop="handleDrop"
        :class="{ 'drag-active': dragActive }"
    >
      <div v-if="dragActive" class="drag-overlay">
        <div class="drag-content">
          📎 释放文件以上传
        </div>
      </div>

      <div
          v-for="(msg, index) in messages"
          :key="index"
          :class="msg.className"
          v-html="msg.html"
      ></div>
    </div>

    <!-- 输入区域 -->
    <div class="input-area">
      <input
          type="text"
          v-model="inputMessage"
          @keypress="handleKeyPress"
          placeholder="输入消息或拖拽文件到上方区域..."
          :disabled="status !== 'connected'"
      />
      <div class="button-group">
        <button @click="openFileSelector" class="file-btn" title="上传文件">
          📎
        </button>
        <button
            @click="sendMessage"
            :disabled="status !== 'connected' || !inputMessage.trim()"
            id="sendBtn"
        >
          发送
        </button>
        <button @click="newSession" id="newBtn">
          新建会话
        </button>
      </div>
    </div>

    <!-- 隐藏的文件输入 -->
    <input
        type="file"
        ref="fileInput"
        style="display: none"
        @change="handleFileSelect"
    />

    <!-- 状态栏 -->
    <div :class="['status', statusClass]">
      状态: {{ statusText }}
      <span v-if="dragActive" style="margin-left: 10px; color: #2196f3;">
        📎 拖拽文件到此处上传
      </span>
    </div>
  </div>
</template>

<script setup>
import {ref, computed, onMounted, onUnmounted, nextTick} from 'vue'

// 响应式数据
const ws = ref(null)
const sessionId = ref(null)
const messages = ref([])
const inputMessage = ref('')
const status = ref('connecting') // connecting, connected, processing, disconnected
const outputRef = ref(null)
const reconnectAttempts = ref(0)
const currentResponseIndex = ref(-1)
const currentResponseContent = ref('')

const maxReconnectAttempts = 5
const API_BASE_URL = 'http://localhost:5000/api'

// 计算状态文本和样式
const statusText = computed(() => {
  switch (status.value) {
    case 'connecting':
      return '正在连接...'
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

const statusClass = computed(() => {
  return status.value
})

// 工具函数：HTML转义
const escapeHtml = (text) => {
  const div = document.createElement('div')
  div.textContent = text
  return div.innerHTML
}

// 滚动到底部
const scrollToBottom = async () => {
  await nextTick()
  if (outputRef.value) {
    outputRef.value.scrollTop = outputRef.value.scrollHeight
  }
}

// 添加消息
const addMessage = (sender, content, className, isIndented = false) => {
  const timestamp = new Date().toLocaleTimeString()
  const prefix = isIndented ? '&nbsp;&nbsp;&nbsp;&nbsp;' : ''
  const html = `${prefix}<strong>${escapeHtml(sender)}:</strong> ${escapeHtml(content)} <span style="font-size: 10px; color: #999;">${timestamp}</span>`

  messages.value.push({
    className,
    html
  })
  scrollToBottom()
}

// 创建助手响应容器
const createResponseContainer = () => {
  currentResponseContent.value = ''
  messages.value.push({
    className: 'assistant',
    html: '<strong>助手:</strong> '
  })
  currentResponseIndex.value = messages.value.length - 1
  scrollToBottom()
}

// 追加内容到最后一个助手消息
const appendToLastMessage = (content) => {
  currentResponseContent.value += content
  if (currentResponseIndex.value !== -1) {
    messages.value[currentResponseIndex.value].html = `<strong>助手:</strong> ${escapeHtml(currentResponseContent.value)}`
    scrollToBottom()
  } else {
    createResponseContainer()
    appendToLastMessage(content)
  }
}

// 关闭WebSocket
const closeWebSocket = () => {
  if (ws.value && ws.value.readyState === WebSocket.OPEN) {
    console.log('关闭现有WebSocket连接...')
    ws.value.close()
  }
}

// 新建会话
const newSession = () => {
  if (confirm('确定要创建新会话吗？当前会话将被清除，页面将刷新以开始全新对话。')) {
    localStorage.removeItem('last_session_id')
    closeWebSocket()
    window.location.reload()
  }
}

// WebSocket连接
const connect = () => {
  status.value = 'connecting'
  const wsUrl = 'ws://localhost:5000/api/chat/ws/message'
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
              addMessage('系统', `新会话ID: ${data.session_id.substring(0, 8)}...（本次会话）`, 'system')
            }
            break

          case 'chunk':
            appendToLastMessage(data.content)
            break

          case 'tool_call':
            addMessage('🔧 工具调用', `${data.tool_name}`, 'tool-call')
            if (data.tool_args && Object.keys(data.tool_args).length > 0) {
              const argsStr = JSON.stringify(data.tool_args, null, 2)
              const preview = argsStr.length > 200 ? argsStr.substring(0, 200) + '...' : argsStr
              addMessage('   参数', preview, 'tool-call', true)
            }
            break

          case 'tool_result':
            const resultPreview = typeof data.result === 'string'
                ? data.result.substring(0, 200)
                : JSON.stringify(data.result).substring(0, 200)
            const statusIcon = data.status === 'error' ? '✗' : '✓'
            addMessage(`${statusIcon} 工具结果`, `${data.tool_name}: ${resultPreview}${resultPreview.length >= 200 ? '...' : ''}`, 'tool-result')
            break

          case 'complete':
            addMessage('完成', '消息处理完成', 'system')
            status.value = 'connected'
            currentResponseIndex.value = -1
            currentResponseContent.value = ''
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

      // 自动重连
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

// 发送消息
const sendMessage = () => {
  const message = inputMessage.value.trim()

  if (!message) {
    addMessage('系统', '请输入消息内容', 'system')
    return
  }

  if (!ws.value || ws.value.readyState !== WebSocket.OPEN) {
    addMessage('错误', 'WebSocket 未连接，请等待连接成功后再试', 'error')
    console.log('WebSocket 状态:', ws.value ? ws.value.readyState : 'null')
    return
  }

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

// 键盘事件处理
const handleKeyPress = (e) => {
  if (e.key === 'Enter') {
    sendMessage()
  }
}

// 清理保存的会话ID
const clearSavedSessionId = () => {
  localStorage.removeItem('last_session_id')
  console.log('已清除保存的会话ID，开始全新会话')
}

// 生命周期钩子
onMounted(() => {
  console.log('页面加载，初始化全新会话...')
  clearSavedSessionId()
  connect()

  // 页面关闭前关闭WebSocket
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


const dragActive = ref(false) // 拖拽激活状态
const fileInput = ref(null)   // 文件输入引用

// 发送文件
const sendFile = (file) => {
  if (!ws.value || ws.value.readyState !== WebSocket.OPEN) {
    addMessage('错误', 'WebSocket 未连接，无法上传文件', 'error')
    return false
  }

  const reader = new FileReader()

  reader.onload = () => {
    // 准备元数据
    const metadata = {
      filename: file.name,
      filetype: file.type,
      size: file.size,
      timestamp: new Date().toISOString()
    }

    // 编码元数据为 JSON 字符串
    const metadataStr = JSON.stringify(metadata)
    const metadataBytes = new TextEncoder().encode(metadataStr)
    const metadataLength = metadataBytes.length

    // 构建二进制数据包
    // 格式：[4字节元数据长度][元数据JSON][文件二进制数据]
    const buffer = new ArrayBuffer(4 + metadataLength + file.size)
    const view = new DataView(buffer)

    // 写入元数据长度（大端序）
    view.setUint32(0, metadataLength, false)

    // 写入元数据
    const metadataBuffer = new Uint8Array(buffer, 4, metadataLength)
    metadataBuffer.set(metadataBytes)

    // 写入文件数据
    const fileBuffer = new Uint8Array(buffer, 4 + metadataLength, file.size)
    fileBuffer.set(new Uint8Array(reader.result))

    // 发送二进制数据
    ws.value.send(buffer)

    // 在聊天界面显示文件上传消息
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

// 处理拖拽
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
    // 可选：添加文件大小限制（如 100MB）
    if (file.size > 100 * 1024 * 1024) {
      addMessage('错误', `文件太大: ${file.name} (超过100MB限制)`, 'error')
      return
    }
    sendFile(file)
  }
}

// 打开文件选择器
const openFileSelector = () => {
  fileInput.value.click()
}

// 处理文件选择
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
  // 清空 input，以便重新选择同一文件
  fileInput.value.value = ''
}


// 格式化文件大小（字节 -> 可读格式）
const formatFileSize = (bytes) => {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

// 接收文件上传成功的消息
const handleFileReceived = (data) => {
  const fileInfo = data.file_info

  const formattedSize = formatFileSize(fileInfo.size)

  // 显示成功消息
  addMessage('系统', `✅ 文件上传成功: ${fileInfo.name} (${formattedSize})`, 'system')

  // 显示文件保存信息
  addMessage('系统', `📁 保存为: ${fileInfo.saved_name}`, 'system', true)

  // 显示访问路径（如果有 URL）
  if (fileInfo.url) {
    addMessage('系统', `🔗 访问路径: ${fileInfo.url}`, 'system', true)
  }

  // 可选：显示完整信息（点击可展开）
  console.log('文件上传成功详情:', fileInfo)
}

</script>

<style scoped>
.output {
  position: relative;
  margin-top: 20px;
  border: 1px solid #ccc;
  padding: 10px;
  min-height: 400px;
  max-height: 500px;
  overflow-y: auto;
  background-color: #f9f9f9;
  transition: all 0.3s ease;
}

.output.drag-active {
  border: 2px dashed #2196f3;
  background-color: #e3f2fd;
}

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
  pointer-events: none;
}

.drag-content {
  background-color: white;
  padding: 20px 40px;
  border-radius: 10px;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
  font-size: 18px;
  color: #2196f3;
  font-weight: bold;
}

.input-area {
  margin-top: 20px;
  display: flex;
  gap: 10px;
}

.input-area input {
  flex: 1;
  padding: 10px;
  font-size: 14px;
  border: 1px solid #ccc;
  border-radius: 4px;
}

.button-group {
  display: flex;
  gap: 10px;
}

.file-btn {
  background-color: #9c27b0;
  color: white;
  font-size: 16px;
  width: 40px;
}

.file-btn:hover {
  background-color: #7b1fa2;
}

.tool-call {
  color: #0066cc;
  margin-left: 10px;
  font-size: 0.9em;
}

.tool-result {
  color: #009900;
  margin-left: 20px;
  font-size: 0.9em;
}

.error {
  color: #cc0000;
}

.system {
  color: #666666;
  font-style: italic;
}

.user {
  color: #000000;
  font-weight: bold;
}

.assistant {
  color: #000000;
}

.warning {
  color: #ff9900;
  font-style: italic;
}

.input-area {
  margin-top: 20px;
  display: flex;
  gap: 10px;
}

.input-area input {
  flex: 1;
  padding: 10px;
  font-size: 14px;
  border: 1px solid #ccc;
  border-radius: 4px;
}

.input-area input:focus {
  outline: none;
  border-color: #2196f3;
}

.button-group {
  display: flex;
  gap: 10px;
}

button {
  padding: 10px 20px;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.3s ease;
  border: none;
  border-radius: 4px;
}

button:hover:not(:disabled) {
  opacity: 0.8;
}

button:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

#newBtn {
  background-color: #4caf50;
  color: white;
}

#sendBtn {
  background-color: #2196f3;
  color: white;
}

.status {
  margin-top: 10px;
  padding: 5px;
  font-size: 12px;
  color: #666;
}

.status.connected {
  color: #4caf50;
}

.status.disconnected {
  color: #f44336;
}

.status.processing {
  color: #ff9800;
}
</style>