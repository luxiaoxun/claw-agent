<template>
  <div class="skill-management">
    <div class="skill-header">
      <h2>Skill 管理</h2>
      <el-button type="primary" @click="triggerImport">
        <el-icon><Upload /></el-icon>
        导入
      </el-button>
      <input
        ref="fileInput"
        type="file"
        accept=".zip"
        style="display: none"
        @change="handleFileChange"
      />
    </div>

    <div v-if="loading" class="loading">
      <el-icon class="is-loading"><Loading /></el-icon>
      加载中...
    </div>

    <div v-else-if="error" class="error">
      {{ error }}
    </div>

    <div v-else class="skill-grid">
      <el-card
        v-for="skill in skills"
        :key="skill.name"
        class="skill-card"
        shadow="hover"
        @click="showSkillDetail(skill)"
      >
        <div class="skill-name">{{ skill.name }}</div>
        <div class="skill-description">{{ skill.description }}</div>
      </el-card>
    </div>

    <!-- Skill 详情对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="currentSkill?.name"
      width="800px"
      :close-on-click-modal="false"
    >
      <div v-if="currentSkill" class="skill-detail">
        <div class="skill-meta">
          <el-tag size="small" type="info">{{ currentSkill.name }}</el-tag>
          <span class="skill-desc">{{ currentSkill.description }}</span>
        </div>
        <el-divider />
        <div class="skill-content">
          <pre>{{ currentSkill.content }}</pre>
        </div>
      </div>
      <template #footer>
        <el-button @click="dialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElIcon, ElCard, ElDialog, ElButton, ElTag, ElDivider, ElMessage, ElMessageBox } from 'element-plus'
import { Loading, Upload } from '@element-plus/icons-vue'
import { api, skillApi } from '../utils/api'

const skills = ref([])
const loading = ref(true)
const error = ref('')
const dialogVisible = ref(false)
const currentSkill = ref(null)
const fileInput = ref(null)

const fetchSkills = async () => {
  loading.value = true
  error.value = ''
  try {
    const data = await skillApi.list()
    if (data && data.skills) {
      skills.value = data.skills
    }
  } catch (e) {
    error.value = `加载失败: ${e.message}`
    console.error('加载Skill列表失败:', e)
  } finally {
    loading.value = false
  }
}

const showSkillDetail = async (skill) => {
  currentSkill.value = null
  dialogVisible.value = true

  try {
    const data = await skillApi.get(skill.name)
    if (data) {
      currentSkill.value = data
    }
  } catch (e) {
    console.error('加载Skill详情失败:', e)
    currentSkill.value = skill // fallback to list data
  }
}

const triggerImport = () => {
  fileInput.value.click()
}

const handleFileChange = async (event) => {
  const file = event.target.files[0]
  if (!file) return

  try {
    // Preview the skill package first
    const previewFormData = new FormData()
    previewFormData.append('file', file)

    const previewResult = await skillApi.preview(previewFormData)

    if (previewResult && previewResult.exists) {
      // Ask user if they want to overwrite
      try {
        await ElMessageBox.confirm(
          `Skill "${previewResult.name}" 已存在，是否覆盖？`,
          '确认覆盖',
          {
            confirmButtonText: '覆盖',
            cancelButtonText: '取消',
            type: 'warning'
          }
        )
      } catch {
        event.target.value = ''
        return
      }
    }

    // Proceed with import
    const formData = new FormData()
    formData.append('file', file)

    const result = await skillApi.import(formData)
    if (result && result.exists) {
      ElMessage.success(`Skill "${result.name}" 覆盖成功`)
    } else {
      ElMessage.success('Skill导入成功')
    }
    fetchSkills()
  } catch (e) {
    ElMessage.error(`导入失败: ${e.message}`)
  } finally {
    event.target.value = ''
  }
}

onMounted(() => {
  fetchSkills()
})
</script>

<style scoped>
.skill-management {
  height: 100%;
  padding: 20px;
  overflow-y: auto;
  background-color: #f5f5f5;
}

.skill-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.skill-header h2 {
  margin: 0;
  color: #303133;
  font-size: 16px;
  font-weight: 600;
}

.loading, .error {
  text-align: center;
  padding: 40px;
  color: #909399;
}

.error {
  color: #f56c6c;
}

.skill-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}

.skill-card {
  cursor: pointer;
  transition: all 0.3s;
}

.skill-card:hover {
  transform: translateY(-2px);
}

.skill-card :deep(.el-card__body) {
  padding: 16px;
}

.skill-name {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 8px;
}

.skill-description {
  font-size: 13px;
  color: #909399;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.skill-detail {
  max-height: 60vh;
  overflow-y: auto;
}

.skill-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.skill-desc {
  color: #606266;
  font-size: 14px;
}

.skill-content {
  background: #fafafa;
  padding: 16px;
  border-radius: 8px;
}

.skill-content pre {
  margin: 0;
  white-space: pre-wrap;
  word-wrap: break-word;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 13px;
  line-height: 1.6;
  color: #333;
}
</style>