<template>
  <div class="workspace-browser">
    <!-- 头部：标题和操作 -->
    <div class="browser-header">
      <span class="header-title">工作空间</span>
      <div class="header-actions">
        <el-button :icon="Refresh" circle size="small" @click="refreshCurrentPath" />
      </div>
    </div>

    <!-- 路径导航栏 -->
    <div class="path-nav">
      <el-breadcrumb separator="/">
        <el-breadcrumb-item
          v-for="(crumb, index) in pathCrumbs"
          :key="crumb.path"
          @click.native="navigateTo(crumb.path)"
          :class="{ 'clickable': index < pathCrumbs.length - 1 }"
        >
          {{ crumb.name }}
        </el-breadcrumb-item>
      </el-breadcrumb>
    </div>

    <!-- 文件列表区域 -->
    <div class="file-list-container" v-loading="loading">
      <div class="file-grid" v-if="!loading && items.length > 0">
        <div
          v-for="item in items"
          :key="item.path"
          class="file-item"
          :class="{ 'is-directory': item.is_directory }"
          @click="handleItemClick(item)"
          @dblclick="handleItemDoubleClick(item)"
        >
          <div class="file-icon">
            <el-icon v-if="item.is_directory" :size="48"><Folder /></el-icon>
            <el-icon v-else :size="48"><Document /></el-icon>
          </div>
          <div class="file-name">{{ item.name }}</div>
          <el-tooltip
            v-if="!item.is_directory"
            :content="`大小: ${formatSize(item.size)}\n修改时间: ${formatTime(item.modified_time)}`"
            placement="bottom"
            effect="light"
          >
            <div class="file-info">
              <span class="file-size">{{ formatSize(item.size) }}</span>
            </div>
          </el-tooltip>
          <div v-else class="file-info">
            </div>
        </div>
      </div>

      <el-empty v-else-if="!loading" description="该目录下没有文件" />

      <!-- 文件详情对话框 -->
      <el-dialog v-model="detailVisible" title="文件详情" width="500px" :destroy-on-close="true">
        <div class="file-detail" v-if="currentFile">
          <div class="detail-row">
            <span class="detail-label">文件名：</span>
            <span class="detail-value">{{ currentFile.name }}</span>
          </div>
          <div class="detail-row">
            <span class="detail-label">路径：</span>
            <span class="detail-value">{{ currentFile.path }}</span>
          </div>
          <div class="detail-row">
            <span class="detail-label">类型：</span>
            <span class="detail-value">{{ currentFile.is_directory ? '目录' : '文件' }}</span>
          </div>
          <div class="detail-row" v-if="!currentFile.is_directory">
            <span class="detail-label">大小：</span>
            <span class="detail-value">{{ formatSize(currentFile.size) }}</span>
          </div>
          <div class="detail-row">
            <span class="detail-label">修改时间：</span>
            <span class="detail-value">{{ formatTime(currentFile.modified_time) }}</span>
          </div>
        </div>
      </el-dialog>

      <!-- 文件预览对话框 -->
      <el-dialog v-model="previewVisible" title="文件预览" width="80%" :destroy-on-close="true">
        <div class="file-preview">
          <div class="preview-header">
            <span class="file-name">{{ previewFile.name }}</span>
            <span class="file-size">{{ formatSize(previewFile.size) }}</span>
          </div>
          <el-scrollbar>
            <pre class="file-content">{{ fileContent }}</pre>
          </el-scrollbar>
        </div>
      </el-dialog>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, Folder, Document } from '@element-plus/icons-vue'
import { api, workspaceApi } from '../utils/api'

const loading = ref(false)
const items = ref([])
const currentPath = ref('')
const workspaceRoot = ref('')

const previewVisible = ref(false)
const previewFile = ref({ name: '', size: 0 })
const fileContent = ref('')

const detailVisible = ref(false)
const currentFile = ref(null)

const pathCrumbs = computed(() => {
  if (!currentPath.value || !workspaceRoot.value) return []

  // 统一使用正斜杠处理路径比较
  const normalizedCurrent = currentPath.value.replace(/\\/g, '/')
  const normalizedRoot = workspaceRoot.value.replace(/\\/g, '/')

  // 计算相对路径
  const relativePath = normalizedCurrent.substring(normalizedRoot.length).replace(/^[/\\]/, '')

  // 第一个面包屑：工作空间根目录（使用短名称）
  const rootName = normalizedRoot.split('/').pop() || 'workspace'
  const crumbs = [{ name: rootName, path: workspaceRoot.value }]

  // 如果有子目录，添加子目录面包屑
  if (relativePath) {
    const parts = relativePath.split(/[/\\]/).filter(Boolean)
    let accumulatedPath = workspaceRoot.value
    for (const part of parts) {
      // 统一使用正斜杠拼接路径
      accumulatedPath = (accumulatedPath.replace(/[/\\]+$/, '') + '/' + part).replace(/[/\\]+$/, '')
      crumbs.push({
        name: part,
        path: accumulatedPath
      })
    }
  }

  return crumbs
})

const fetchDirectory = async (path) => {
  loading.value = true
  try {
    const data = await workspaceApi.list(path)
    if (data && data.items) {
      items.value = data.items.sort((a, b) => {
        if (a.is_directory !== b.is_directory) {
          return a.is_directory ? -1 : 1
        }
        return a.name.localeCompare(b.name)
      })
      currentPath.value = data.path
      if (!workspaceRoot.value) {
        workspaceRoot.value = data.path
      }
    }
  } catch (e) {
    console.error('获取目录内容失败:', e)
    ElMessage.error('获取目录内容失败')
  } finally {
    loading.value = false
  }
}

const handleItemClick = (item) => {
  if (item.is_directory) {
    fetchDirectory(item.path)
    return
  }
  currentFile.value = item
  detailVisible.value = true
}

const handleItemDoubleClick = (item) => {
  if (item.is_directory) {
    fetchDirectory(item.path)
  } else {
    previewFile.value = { name: item.name, size: item.size }
    workspaceApi.read(item.path).then(resp => {
      if (resp) {
        previewFile.value = { name: resp.name, size: resp.size }
        fileContent.value = resp.content || ''
        previewVisible.value = true
      }
    }).catch(() => {
      ElMessage.error('读取文件失败')
    })
  }
}

const navigateTo = (path) => {
  if (path === currentPath.value) return
  // 限制不能超出工作空间根目录
  const normalizedRoot = workspaceRoot.value.replace(/\\/g, '/')
  const normalizedPath = path.replace(/\\/g, '/')
  if (!normalizedPath.startsWith(normalizedRoot)) {
    ElMessage.warning('不能访问工作空间以外的目录')
    return
  }
  fetchDirectory(path)
}

const formatSize = (bytes) => {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let size = bytes
  let unitIndex = 0
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024
    unitIndex++
  }
  return `${size.toFixed(1)} ${units[unitIndex]}`
}

const formatTime = (timestamp) => {
  if (!timestamp) return '-'
  const date = new Date(timestamp * 1000)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

const refreshCurrentPath = () => {
  if (currentPath.value) {
    fetchDirectory(currentPath.value)
  }
}

onMounted(() => {
  workspaceApi.tree().then(data => {
    if (data && data.workspace_dir) {
      fetchDirectory(data.workspace_dir)
    }
  })
})
</script>

<style scoped>
.workspace-browser {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  background-color: #fff;
}

.browser-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid #e4e7ed;
}

.header-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.path-nav {
  display: flex;
  align-items: center;
  padding: 8px 16px;
  background: #f5f7fa;
  border-bottom: 1px solid #e4e7ed;
}

.path-nav :deep(.el-breadcrumb) {
  flex: 1;
}

.path-nav :deep(.clickable) {
  cursor: pointer;
  color: #409eff;
}

.path-nav :deep(.clickable:hover) {
  color: #66b1ff;
}

.file-list-container {
  flex: 1;
  overflow: auto;
  padding: 16px;
}

.file-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 16px;
}

.file-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 16px 8px;
  border-radius: 8px;
  cursor: pointer;
  transition: background-color 0.2s;
  border: 1px solid transparent;
}

.file-item:hover {
  background-color: #f5f7fa;
  border-color: #e4e7ed;
}

.file-item.is-directory {
  cursor: pointer;
}

.file-icon {
  margin-bottom: 8px;
  color: #909399;
}

.file-item.is-directory .file-icon {
  color: #e6a23c;
}

.file-name {
  font-size: 13px;
  color: #303133;
  text-align: center;
  word-break: break-all;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  line-height: 1.4;
  height: 2.8em;
}

.file-info {
  margin-top: 4px;
  font-size: 12px;
  color: #909399;
}

.file-detail {
  padding: 8px 0;
}

.detail-row {
  display: flex;
  padding: 8px 0;
  border-bottom: 1px solid #f0f0f0;
}

.detail-row:last-child {
  border-bottom: none;
}

.detail-label {
  width: 100px;
  color: #909399;
  flex-shrink: 0;
}

.detail-value {
  color: #303133;
  word-break: break-all;
}

.file-preview {
  height: 60vh;
  display: flex;
  flex-direction: column;
}

.preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 12px;
  border-bottom: 1px solid #e4e7ed;
  margin-bottom: 12px;
}

.file-name {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.file-size {
  font-size: 13px;
  color: #909399;
}

.file-content {
  background: #f5f7fa;
  padding: 16px;
  border-radius: 4px;
  font-size: 13px;
  line-height: 1.6;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
  flex: 1;
  margin: 0;
}
</style>