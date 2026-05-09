<template>
  <div>
    <h2>AI Agent测试 - Vue版</h2>

    <!-- 消息输出区域 -->
    <div class="output" ref="outputRef">
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
        placeholder="输入消息..."
        :disabled="status !== 'connected'"
      />
      <div class="button-group">
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

    <!-- 状态栏 -->
    <div :class="['status', statusClass]">
      状态: {{ statusText }}
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'

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
  switch(status.value) {
    case 'connecting': return '正在连接...'
    case 'connected': return '已连接'
    case 'processing': return '处理中...'
    case 'disconnected': return '已断开'
    default: return '未知'
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

        switch(data.type) {
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
        addMessage('系统', `${delay/1000}秒后尝试重连... (${reconnectAttempts.value}/${maxReconnectAttempts})`, 'system')
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
</script>

<style scoped>
.output {
  margin-top: 20px;
  border: 1px solid #ccc;
  padding: 10px;
  min-height: 400px;
  max-height: 500px;
  overflow-y: auto;
  background-color: #f9f9f9;
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