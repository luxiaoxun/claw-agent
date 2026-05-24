<template>
  <div class="session-sidebar">
    <div class="sidebar-header">
      <span class="header-title">会话管理</span>
    </div>

    <div class="search-box">
      <el-input
        v-model="searchQuery"
        placeholder="搜索会话..."
        clearable
        :prefix-icon="Search"
        @input="handleSearch"
      />
    </div>

    <div class="new-session-btn">
      <el-button type="primary" :icon="Plus" @click="createNewSession" style="width: 100%;">
        新建会话
      </el-button>
    </div>

    <el-scrollbar
      class="session-list"
      v-loading="loading"
      @reach-bottom="loadMore"
      ref="scrollbarRef"
    >
      <div
        v-for="session in filteredSessions"
        :key="session.session_id"
        :class="['session-item', { active: currentSessionId === session.session_id }]"
        @click="selectSession(session)"
      >
        <el-icon class="session-icon"><ChatDotRound /></el-icon>
        <div class="session-info">
          <div class="session-title">{{ session.title || '新会话' }}</div>
          <div class="session-time">{{ formatTime(session.update_time) }}</div>
        </div>
        <el-dropdown trigger="click" @command="(cmd) => handleCommand(cmd, session)">
          <el-button :icon="More" circle size="small" class="more-btn" @click.stop />
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="rename">
                <el-icon><Edit /></el-icon>
                重命名会话
              </el-dropdown-item>
              <el-dropdown-item command="delete">
                <el-icon><Delete /></el-icon>
                删除会话
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>

      <div v-if="loadingMore" class="load-more">
        <el-icon class="is-loading"><Loading /></el-icon>
        加载中...
      </div>

      <div v-else-if="hasMore && !searchQuery" class="load-more">
        <el-button link type="primary" @click="loadMore">加载更多</el-button>
      </div>

      <el-empty
        v-if="!loading && filteredSessions.length === 0"
        :description="searchQuery ? '没有找到匹配的会话' : '暂无会话记录'"
      />
    </el-scrollbar>

    <!-- 重命名对话框 -->
    <el-dialog v-model="renameDialogVisible" title="重命名会话" width="400px">
      <el-input v-model="newSessionTitle" placeholder="请输入新会话名称" />
      <template #footer>
        <el-button @click="renameDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmRename">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { ElMessage, ElMessageBox, ElTooltip } from 'element-plus'
import { Plus, Search, ChatDotRound, Delete, Loading, More, Edit } from '@element-plus/icons-vue'
import dayjs from 'dayjs'
import relativeTime from 'dayjs/plugin/relativeTime'
import 'dayjs/locale/zh-cn'
import { api, sessionApi } from '../utils/api'

dayjs.extend(relativeTime)
dayjs.locale('zh-cn')

const emit = defineEmits(['select-session', 'new-session'])

const PAGE_SIZE = 20

const sessions = ref([])
const loading = ref(false)
const loadingMore = ref(false)
const searchQuery = ref('')
const currentSessionId = ref(null)
const currentOffset = ref(0)
const total = ref(0)
const hasMore = computed(() => sessions.value.length < total.value)
const scrollbarRef = ref(null)

// 重命名相关
const renameDialogVisible = ref(false)
const newSessionTitle = ref('')
const renameSessionId = ref(null)

const filteredSessions = computed(() => {
  if (!searchQuery.value) return sessions.value
  const query = searchQuery.value.toLowerCase()
  return sessions.value.filter(s =>
    (s.title || '').toLowerCase().includes(query)
  )
})

const formatTime = (timeStr) => {
  if (!timeStr) return ''
  return dayjs(timeStr).fromNow()
}

const fetchSessions = async (reset = false) => {
  if (reset) {
    loading.value = true
    currentOffset.value = 0
  } else {
    loadingMore.value = true
  }

  try {
    const data = await sessionApi.list(PAGE_SIZE, currentOffset.value)

    if (data) {
      if (reset) {
        sessions.value = data.sessions
      } else {
        sessions.value = [...sessions.value, ...data.sessions]
      }
      total.value = data.total
      currentOffset.value += data.sessions.length
    }
  } catch (e) {
    console.error('获取会话列表失败:', e)
  } finally {
    loading.value = false
    loadingMore.value = false
  }
}

const loadMore = () => {
  if (!loadingMore.value && hasMore.value && !searchQuery.value) {
    fetchSessions()
  }
}

const handleSearch = () => {
  // Search filtering is handled by computed property
}

const createNewSession = async () => {
  try {
    const data = await sessionApi.create()
    if (data && data.session_id) {
      currentSessionId.value = data.session_id
      emit('new-session', data.session_id)
    } else {
      ElMessage.error('创建会话失败')
    }
  } catch (e) {
    console.error('创建会话失败:', e)
    ElMessage.error('创建会话失败')
  }
}

const selectSession = (session) => {
  currentSessionId.value = session.session_id
  emit('select-session', session.session_id)
}

const handleCommand = (command, session) => {
  if (command === 'rename') {
    showRenameDialog(session)
  } else if (command === 'delete') {
    handleDelete(session.session_id)
  }
}

const showRenameDialog = (session) => {
  renameSessionId.value = session.session_id
  newSessionTitle.value = session.title || ''
  renameDialogVisible.value = true
}

const confirmRename = async () => {
  if (!newSessionTitle.value.trim()) {
    ElMessage.warning('会话名称不能为空')
    return
  }

  const success = await sessionApi.rename(renameSessionId.value, newSessionTitle.value.trim())

  if (success) {
    ElMessage.success('重命名成功')
    // 更新本地列表中的标题
    const session = sessions.value.find(s => s.session_id === renameSessionId.value)
    if (session) {
      session.title = newSessionTitle.value.trim()
    }
    renameDialogVisible.value = false
  }
}

const handleDelete = async (sessionId) => {
  try {
    await ElMessageBox.confirm(
      '确定要删除这个会话吗？',
      '删除确认',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )

    const success = await sessionApi.delete(sessionId)
    if (success) {
      ElMessage.success('删除成功')
      sessions.value = sessions.value.filter(s => s.session_id !== sessionId)
      total.value--
      if (currentSessionId.value === sessionId) {
        currentSessionId.value = null
        emit('new-session')
      }
    }
  } catch (e) {
    if (e !== 'cancel') {
      console.error('删除会话失败:', e)
    }
  }
}

onMounted(() => {
  fetchSessions(true)
})

defineExpose({ fetchSessions })
</script>

<style scoped>
.session-sidebar {
  width: 280px;
  height: 100%;
  background-color: #fafafa;
  border-right: 1px solid #e4e7ed;
  display: flex;
  flex-direction: column;
}

.sidebar-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  border-bottom: 1px solid #e4e7ed;
}

.header-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.search-box {
  padding: 12px 16px;
}

.new-session-btn {
  padding: 0 16px 12px;
}

.session-list {
  flex: 1;
  padding: 8px 12px;
  height: calc(100% - 160px);
}

.session-item {
  display: flex;
  align-items: center;
  padding: 12px;
  margin-bottom: 4px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
}

.session-item:hover {
  background-color: #f5f7fa;
}

.session-item.active {
  background-color: #ecf5ff;
}

.session-icon {
  font-size: 20px;
  color: #909399;
  margin-right: 12px;
}

.session-info {
  flex: 1;
  min-width: 0;
}

.session-title {
  font-size: 14px;
  color: #303133;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 4px;
}

.session-time {
  font-size: 12px;
  color: #909399;
}

.more-btn {
  opacity: 0;
  transition: opacity 0.2s;
}

.session-item:hover .more-btn {
  opacity: 1;
}

.load-more {
  text-align: center;
  padding: 12px;
  color: #909399;
  font-size: 13px;
}
</style>