<template>
  <div class="knowledge-base">
    <!-- 文件上传 input（始终在 DOM 中保证可点击） -->
    <input
      type="file"
      ref="fileInput"
      @change="handleFileChange"
      accept=".pdf,.docx,.doc,.txt"
      style="display:none"
    />

    <!-- 头部 -->
    <div class="kb-header">
      <span class="header-title">知识库管理</span>
      <div class="header-buttons">
        <el-button type="primary" size="small" @click="showCreateDialog">创建知识库</el-button>
        <el-button size="small" @click="loadCollections" :loading="loading">刷新</el-button>
      </div>
    </div>

    <!-- 知识库列表 -->
    <div class="kb-table" v-loading="loading">
      <el-table :data="collections" style="width: 100%" v-if="collections.length > 0">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="name" label="名称" width="180">
          <template #default="{ row }">
            <span class="collection-name">{{ row.name }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="描述" min-width="150" show-overflow-tooltip />
        <el-table-column prop="document_count" label="文档" width="80" align="center" />
        <el-table-column prop="chunk_count" label="块数" width="80" align="center" />
        <el-table-column prop="chunk_size" label="块大小" width="80" align="center" />
        <el-table-column prop="create_time" label="创建时间" width="160">
          <template #default="{ row }">
            {{ formatTime(row.create_time) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="uploadDocument(row)">上传</el-button>
            <el-button link type="primary" size="small" @click="viewDocuments(row)">文档</el-button>
            <el-button link type="primary" size="small" @click="testSearch(row)">检索</el-button>
            <el-button link type="danger" size="small" @click="deleteCollection(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-else description="暂无知识库，点击「创建知识库」开始" />
    </div>

    <!-- 创建知识库对话框 -->
    <el-dialog v-model="createDialogVisible" title="创建知识库" width="450px" :close-on-click-modal="false">
      <el-form :model="form" label-width="100px" ref="formRef">
        <el-form-item label="名称" prop="name" :rules="[{ required: true, message: '请输入名称' }]">
          <el-input v-model="form.name" placeholder="知识库名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="块大小">
          <el-input-number v-model="form.chunk_size" :min="100" :max="2000" />
        </el-form-item>
        <el-form-item label="重叠大小">
          <el-input-number v-model="form.chunk_overlap" :min="0" :max="500" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitCreate" :loading="submitting">创建</el-button>
      </template>
    </el-dialog>

    <!-- 文档列表对话框 -->
    <el-dialog v-model="docsDialogVisible" :title="`文档列表 - ${currentCollection?.name}`" width="750px">
      <div class="doc-header">
        <el-button type="primary" size="small" @click="triggerUpload">上传文档</el-button>
        <span class="doc-tip">支持 PDF、DOCX、DOC、TXT 格式</span>
      </div>
      <el-table :data="documents" v-loading="docsLoading" size="small">
        <el-table-column prop="file_name" label="文件名" width="200" show-overflow-tooltip />
        <el-table-column prop="file_type" label="类型" width="80" />
        <el-table-column prop="file_size" label="大小" width="100">
          <template #default="{ row }">
            {{ formatSize(row.file_size) }}
          </template>
        </el-table-column>
        <el-table-column prop="token_count" label="Token" width="100" align="right" />
        <el-table-column prop="create_time" label="上传时间" width="160">
          <template #default="{ row }">
            {{ formatTime(row.create_time) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="80">
          <template #default="{ row }">
            <el-button link type="danger" size="small" @click="deleteDocument(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <!-- 检索测试对话框 -->
    <el-dialog v-model="searchDialogVisible" :title="`检索测试 - ${currentCollection?.name}`" width="800px">
      <el-input
        v-model="searchQuery"
        type="textarea"
        :rows="2"
        placeholder="输入检索关键词"
      />
      <div class="search-actions">
        <el-button type="primary" size="small" @click="submitSearch" :loading="searching">检索</el-button>
      </div>
      <div class="search-results" v-loading="searching">
        <div v-if="searchResults.length === 0 && !searching" class="no-results">
          输入关键词进行检索测试
        </div>
        <div v-else>
          <div v-for="(result, index) in searchResults" :key="index" class="result-item">
            <div class="result-header">
              <span class="result-score">相似度: {{ (result.score * 100).toFixed(1) }}%</span>
              <span class="result-source">{{ result.document_name }}</span>
            </div>
            <div class="result-content">{{ result.content }}</div>
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, nextTick, defineExpose } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ragApi } from '../utils/api'

// 文件上传 input（放在 Dialog 外确保始终可点击）
const fileInput = ref(null)
const loading = ref(false)
const collections = ref([])
const createDialogVisible = ref(false)
const submitting = ref(false)
const formRef = ref(null)
const form = reactive({
  name: '',
  description: '',
  chunk_size: 500,
  chunk_overlap: 50
})

const docsDialogVisible = ref(false)
const docsLoading = ref(false)
const documents = ref([])
const currentCollection = ref(null)

const searchDialogVisible = ref(false)
const searchQuery = ref('')
const searching = ref(false)
const searchResults = ref([])

const loadCollections = async () => {
  loading.value = true
  try {
    const data = await ragApi.listCollections()
    if (data) {
      collections.value = data.collections || []
    }
  } finally {
    loading.value = false
  }
}

const showCreateDialog = () => {
  form.name = ''
  form.description = ''
  form.chunk_size = 500
  form.chunk_overlap = 50
  createDialogVisible.value = true
}

const submitCreate = async () => {
  if (!form.name.trim()) {
    ElMessage.warning('请输入名称')
    return
  }
  submitting.value = true
  try {
    const ok = await ragApi.createCollection(form)
    if (ok !== null) {
      ElMessage.success('知识库已创建')
      createDialogVisible.value = false
      loadCollections()
    }
  } finally {
    submitting.value = false
  }
}

const deleteCollection = async (row) => {
  try {
    await ElMessageBox.confirm(`确定删除知识库「${row.name}」吗？将同时删除所有文档。`, '确认删除', {
      type: 'warning'
    })
    const ok = await ragApi.deleteCollection(row.id)
    if (ok !== null) {
      ElMessage.success('已删除')
      loadCollections()
    }
  } catch (e) {
    if (e !== 'cancel') console.error(e)
  }
}

const uploadDocument = async (row) => {
  currentCollection.value = row
  await nextTick()
  fileInput.value?.click()
}

const triggerUpload = async () => {
  await nextTick()
  fileInput.value?.click()
}

const handleFileChange = async (e) => {
  const file = e.target.files[0]
  if (!file) return
  if (!currentCollection.value) {
    ElMessage.warning('请先选择一个知识库')
    return
  }
  try {
    const result = await ragApi.uploadDocument(currentCollection.value.id, file)
    if (result) {
      ElMessage.success(`文档已上传，创建了 ${result.chunks_created} 个块`)
      viewDocuments(currentCollection.value)
    }
  } catch (e) {
    console.error('上传失败:', e)
    ElMessage.error('上传失败')
  } finally {
    e.target.value = ''
  }
}

const viewDocuments = async (row) => {
  currentCollection.value = row
  docsDialogVisible.value = true
  docsLoading.value = true
  try {
    const data = await ragApi.listDocuments(row.id)
    if (data) {
      documents.value = data.documents || []
    }
  } finally {
    docsLoading.value = false
  }
}

const deleteDocument = async (row) => {
  try {
    await ElMessageBox.confirm(`确定删除文档「${row.file_name}」吗？`, '确认删除', { type: 'warning' })
    const ok = await ragApi.deleteDocument(currentCollection.value.id, row.id)
    if (ok !== null) {
      ElMessage.success('已删除')
      viewDocuments(currentCollection.value)
    }
  } catch (e) {
    if (e !== 'cancel') console.error(e)
  }
}

const testSearch = (row) => {
  currentCollection.value = row
  searchQuery.value = ''
  searchResults.value = []
  searchDialogVisible.value = true
}

const submitSearch = async () => {
  if (!searchQuery.value.trim()) {
    ElMessage.warning('请输入检索关键词')
    return
  }
  searching.value = true
  try {
    const data = await ragApi.search({
      query: searchQuery.value,
      collection_ids: [currentCollection.value.id],
      top_k: 5,
      similarity_threshold: 0.5
    })
    if (data) {
      searchResults.value = data.results || []
      console.log('[KnowledgeBase] 检索结果:', data.results)
      if (searchResults.value.length === 0) {
        ElMessage.info('未找到相关结果（可尝试降低相似度阈值）')
      } else {
        ElMessage.success(`找到 ${searchResults.value.length} 条相关结果`)
      }
    }
  } finally {
    searching.value = false
  }
}

const formatTime = (isoString) => {
  if (!isoString) return '-'
  return new Date(isoString).toLocaleString('zh-CN')
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

// 暴露方法供外部调用
defineExpose({
  init: () => {
    console.log('[KnowledgeBase] init called')
    loadCollections()
  }
})
</script>

<style scoped>
.knowledge-base {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  background-color: #fff;
}

.kb-header {
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

.header-buttons {
  display: flex;
  gap: 8px;
}

.kb-table {
  flex: 1;
  overflow: auto;
  padding: 16px;
}

.collection-name {
  font-weight: 500;
  color: #303133;
}

.doc-header {
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  gap: 12px;
}

.doc-tip {
  font-size: 12px;
  color: #909399;
}

.search-actions {
  margin: 12px 0;
}

.search-results {
  max-height: 400px;
  overflow-y: auto;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  padding: 12px;
}

.no-results {
  color: #909399;
  text-align: center;
  padding: 20px;
}

.result-item {
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid #f0f0f0;
}

.result-item:last-child {
  margin-bottom: 0;
  padding-bottom: 0;
  border-bottom: none;
}

.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.result-score {
  font-size: 12px;
  color: #67c23a;
  font-weight: 500;
}

.result-source {
  font-size: 12px;
  color: #909399;
}

.result-content {
  font-size: 13px;
  color: #606266;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>