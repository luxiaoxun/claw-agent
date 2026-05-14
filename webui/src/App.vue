<template>
  <div class="app-container">
    <!-- 左侧导航菜单 -->
    <div class="left-nav">
      <div class="nav-header">
        <span class="nav-title">Claw Agent</span>
      </div>
      <div class="nav-menu">
        <div
          :class="['nav-item', { active: currentMenu === 'session' }]"
          @click="switchMenu('session')"
        >
          <el-icon><ChatDotRound /></el-icon>
          <span>会话管理</span>
        </div>
        <div
          :class="['nav-item', { active: currentMenu === 'skill' }]"
          @click="switchMenu('skill')"
        >
          <el-icon><Tools /></el-icon>
          <span>Skill 管理</span>
        </div>
      </div>
    </div>

    <!-- 会话管理内容 -->
    <template v-if="currentMenu === 'session'">
      <SessionSidebar
        ref="sidebarRef"
        @select-session="handleSelectSession"
        @new-session="handleNewSession"
      />
      <div class="main-content">
        <ChatWindow
          ref="chatRef"
          :key="currentSessionId"
          :session-id="currentSessionId"
          @refresh-sessions="handleRefreshSessions"
        />
      </div>
    </template>

    <!-- Skill管理内容 -->
    <template v-else-if="currentMenu === 'skill'">
      <div class="main-content full-width">
        <SkillManagement />
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { ElIcon } from 'element-plus'
import { ChatDotRound, Tools } from '@element-plus/icons-vue'
import SessionSidebar from './components/SessionSidebar.vue'
import ChatWindow from './components/ChatWindow.vue'
import SkillManagement from './components/SkillManagement.vue'

const sidebarRef = ref(null)
const chatRef = ref(null)
const currentSessionId = ref(null)
const currentMenu = ref('session')

const switchMenu = (menu) => {
  if (menu === currentMenu.value) return

  // 切换菜单前关闭当前会话
  if (currentMenu.value === 'session' && currentSessionId.value) {
    closeCurrentSession()
  }
  currentMenu.value = menu
}

const closeCurrentSession = () => {
  if (chatRef.value) {
    chatRef.value.closeSession()
  }
}

const handleSelectSession = (sessionId) => {
  if (currentSessionId.value && currentSessionId.value !== sessionId) {
    closeCurrentSession()
  }
  currentSessionId.value = sessionId
}

const handleNewSession = (sessionId) => {
  if (currentSessionId.value) {
    closeCurrentSession()
  }
  currentSessionId.value = sessionId
}

const handleRefreshSessions = () => {
  if (sidebarRef.value) {
    sidebarRef.value.fetchSessions(true)
  }
}

// 页面刷新或关闭时关闭当前会话
window.addEventListener('beforeunload', () => {
  if (chatRef.value) {
    chatRef.value.closeSession()
  }
})
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html, body {
  width: 100%;
  height: 100%;
  overflow: hidden;
}

#app {
  width: 100%;
  height: 100%;
}

.app-container {
  display: flex;
  width: 100%;
  height: 100%;
}

/* 左侧导航 */
.left-nav {
  width: 200px;
  height: 100%;
  background: #304156;
  display: flex;
  flex-direction: column;
}

.nav-header {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-bottom: 1px solid #3d4a5c;
}

.nav-title {
  color: #fff;
  font-size: 18px;
  font-weight: 600;
}

.nav-menu {
  flex: 1;
  padding: 8px 0;
}

.nav-item {
  display: flex;
  align-items: center;
  padding: 12px 20px;
  color: #bfcbd9;
  cursor: pointer;
  transition: all 0.3s;
  gap: 12px;
}

.nav-item:hover {
  background: #263445;
  color: #fff;
}

.nav-item.active {
  background: #409eff;
  color: #fff;
}

.nav-item .el-icon {
  font-size: 18px;
}

.nav-item span {
  font-size: 14px;
}

.main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.main-content.full-width {
  width: 100%;
}
</style>