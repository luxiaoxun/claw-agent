<template>
  <div class="channel-management">
    <div class="header">
      <h2>消息通道</h2>
      <div class="header-buttons">
        <el-button type="primary" @click="showCreateDialog">创建通道</el-button>
        <el-button type="primary" @click="loadChannels" :loading="loading">刷新列表</el-button>
      </div>
    </div>

    <!-- 通道列表 -->
    <el-table :data="channels" style="width: 100%" v-loading="loading">
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="name" label="名称" width="180" />
      <el-table-column prop="platform" label="平台" width="100">
        <template #default="{ row }">
          <el-tag :type="row.platform === 'feishu' ? 'primary' : 'success'">
            {{ row.platform === 'feishu' ? '飞书' : '企业微信' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="description" label="描述" min-width="150" show-overflow-tooltip />
      <el-table-column prop="enabled" label="状态" width="100">
        <template #default="{ row }">
          <el-switch
            :model-value="row.enabled === 1"
            @change="toggleEnabled(row)"
            :disabled="row.id === editingId"
          />
        </template>
      </el-table-column>
      <el-table-column prop="status_info.status" label="连接状态" width="120">
        <template #default="{ row }">
          <el-tag :type="getStatusType(row.status_info?.status)">
            {{ getStatusText(row.status_info?.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="create_time" label="创建时间" width="160">
        <template #default="{ row }">
          {{ formatTime(row.create_time) }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="220" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" size="small" @click="editChannel(row)">编辑</el-button>
          <el-button link type="warning" size="small" @click="restartChannel(row)">重启</el-button>
          <el-button link type="danger" size="small" @click="deleteChannel(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 创建/编辑对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEditing ? '编辑通道' : '创建通道'"
      width="500px"
    >
      <el-form :model="form" label-width="100px">
        <el-form-item label="平台" required>
          <el-select v-model="form.platform" :disabled="isEditing" style="width: 100%">
            <el-option label="飞书" value="feishu" />
            <el-option label="企业微信" value="wecom" />
          </el-select>
        </el-form-item>

        <el-form-item label="名称" required>
          <el-input v-model="form.name" placeholder="如：飞书测试机器人" />
        </el-form-item>

        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" placeholder="通道描述" />
        </el-form-item>

        <!-- 飞书配置 -->
        <template v-if="form.platform === 'feishu'">
          <el-form-item label="App ID" required>
            <el-input v-model="form.config.app_id" placeholder="飞书 App ID" />
          </el-form-item>
          <el-form-item label="App Secret" required>
            <el-input v-model="form.config.app_secret" placeholder="飞书 App Secret" show-password />
          </el-form-item>
          <el-form-item label="Verification Token">
            <el-input v-model="form.config.verification_token" placeholder="飞书 Verification Token" />
          </el-form-item>
          <el-form-item label="Encrypt Key">
            <el-input v-model="form.config.encrypt_key" placeholder="飞书 Encrypt Key" show-password />
          </el-form-item>
        </template>

        <!-- 企业微信配置 -->
        <template v-if="form.platform === 'wecom'">
          <el-form-item label="Bot ID" required>
            <el-input v-model="form.config.bot_id" placeholder="企业微信 Bot ID" />
          </el-form-item>
          <el-form-item label="Bot Secret" required>
            <el-input v-model="form.config.bot_secret" placeholder="企业微信 Bot Secret" show-password />
          </el-form-item>
        </template>

        <el-form-item label="启用">
          <el-switch v-model="form.enabled" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitForm" :loading="submitting">
          {{ isEditing ? '保存' : '创建' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { channelApi } from '../utils/api'

const loading = ref(false)
const channels = ref([])
const dialogVisible = ref(false)
const isEditing = ref(false)
const editingId = ref(null)
const submitting = ref(false)

const defaultConfig = {
  feishu: { app_id: '', app_secret: '', verification_token: '', encrypt_key: '' },
  wecom: { bot_id: '', bot_secret: '' }
}

const form = reactive({
  platform: 'feishu',
  name: '',
  description: '',
  config: { ...defaultConfig.feishu },
  enabled: false
})

const loadChannels = async () => {
  loading.value = true
  try {
    const data = await channelApi.list()
    if (data) {
      channels.value = data.channels || []
    }
  } catch (e) {
    console.error('加载通道列表失败:', e)
  } finally {
    loading.value = false
  }
}

const resetForm = () => {
  form.platform = 'feishu'
  form.name = ''
  form.description = ''
  form.config = { ...defaultConfig.feishu }
  form.enabled = false
}

const showCreateDialog = () => {
  isEditing.value = false
  editingId.value = null
  resetForm()
  dialogVisible.value = true
}

const editChannel = (row) => {
  isEditing.value = true
  editingId.value = row.id
  form.platform = row.platform
  form.name = row.name
  form.description = row.description || ''
  form.enabled = row.enabled === 1
  form.config = { ...row.config }
  dialogVisible.value = true
}

const submitForm = async () => {
  if (!form.name.trim()) {
    ElMessage.warning('请输入通道名称')
    return
  }

  submitting.value = true
  try {
    const config = { ...form.config }

    if (isEditing.value) {
      const data = await channelApi.update(editingId.value, {
        name: form.name,
        config,
        description: form.description,
        enabled: form.enabled ? 1 : 0
      })
      if (data) {
        ElMessage.success('通道已更新')
        dialogVisible.value = false
        loadChannels()
      }
    } else {
      const data = await channelApi.create(
        form.platform,
        form.name,
        config,
        form.description,
        form.enabled ? 1 : 0
      )
      if (data) {
        ElMessage.success('通道已创建')
        dialogVisible.value = false
        loadChannels()
      }
    }
  } catch (e) {
    console.error('保存通道失败:', e)
  } finally {
    submitting.value = false
  }
}

const deleteChannel = async (row) => {
  try {
    await ElMessageBox.confirm(`确定删除通道"${row.name}"吗?`, '确认删除', {
      type: 'warning'
    })
    const ok = await channelApi.delete(row.id)
    if (ok !== null) {
      ElMessage.success('通道已删除')
      loadChannels()
    }
  } catch (e) {
    if (e !== 'cancel') {
      console.error('删除通道失败:', e)
    }
  }
}

const toggleEnabled = async (row) => {
  try {
    const newEnabled = row.enabled === 1 ? 0 : 1
    if (newEnabled === 1) {
      await channelApi.enable(row.id)
    } else {
      await channelApi.disable(row.id)
    }
    ElMessage.success(newEnabled ? '通道已启用' : '通道已停用')
    loadChannels()
  } catch (e) {
    console.error('切换通道状态失败:', e)
  }
}

const restartChannel = async (row) => {
  try {
    await ElMessageBox.confirm(`确定要重启通道"${row.name}"吗?`, '确认重启', {
      type: 'warning'
    })
    await channelApi.restart(row.id)
    ElMessage.success('通道已重启')
    loadChannels()
  } catch (e) {
    if (e !== 'cancel') {
      console.error('重启通道失败:', e)
    }
  }
}

const getStatusType = (status) => {
  switch (status) {
    case 'connected': return 'success'
    case 'error': return 'danger'
    default: return 'info'
  }
}

const getStatusText = (status) => {
  switch (status) {
    case 'connected': return '已连接'
    case 'disconnected': return '未连接'
    case 'error': return '错误'
    default: return '未知'
  }
}

const formatTime = (isoString) => {
  if (!isoString) return '-'
  const d = new Date(isoString)
  return d.toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

// Watch platform change to reset config
import { watch } from 'vue'
watch(() => form.platform, (newPlatform) => {
  form.config = { ...defaultConfig[newPlatform] }
})

onMounted(() => {
  loadChannels()
})
</script>

<style scoped>
.channel-management {
  padding: 20px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.header h2 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.header-buttons {
  display: flex;
  gap: 8px;
}
</style>