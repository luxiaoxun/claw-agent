<template>
  <div class="app-container">
    <SessionSidebar
      ref="sidebarRef"
      @select-session="handleSelectSession"
      @new-session="handleNewSession"
    />
    <div class="main-content">
      <ChatInterface
        ref="chatRef"
        :key="currentSessionId"
        :session-id="currentSessionId"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import SessionSidebar from './components/SessionSidebar.vue'
import ChatInterface from './components/ChatInterface.vue'

const sidebarRef = ref(null)
const chatRef = ref(null)
const currentSessionId = ref(null)

const closeCurrentSession = () => {
  if (chatRef.value) {
    chatRef.value.closeSession()
  }
}

const handleSelectSession = (sessionId) => {
  // 关闭当前会话后再打开新会话
  if (currentSessionId.value && currentSessionId.value !== sessionId) {
    closeCurrentSession()
  }
  currentSessionId.value = sessionId
}

const handleNewSession = (sessionId) => {
  // 关闭当前会话后再打开新会话
  if (currentSessionId.value) {
    closeCurrentSession()
  }
  currentSessionId.value = sessionId
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

.main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
</style>