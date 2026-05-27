# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Soma is a Python-based AI agent with a Vue 3 web UI. It provides chat-based interaction with LLM-powered agents that can use tools, skills, and knowledge bases to accomplish tasks.

## Development Commands

### Backend (Python/FastAPI)
```bash
uv sync
uv run uvicorn soma.main:app --host 0.0.0.0 --port 5000
```

### Frontend (Vue 3/Vite)
```bash
cd webui
npm install
npm run dev      # http://localhost:5173
npm run build
```

## Architecture

```
┌─────────────────────────────┐     ┌─────────────────────────────┐
│     前端 Vue 3 + Vite        │     │  后端 Python FastAPI         │
│  SessionSidebar + ChatWindow│────▶│  ChatService → SessionManager│
│  Workspace (文件/技能/知识库) │     │         → DeepAgent         │
└─────────────────────────────┘     └─────────────────────────────┘
```

- **DeepAgent**: ReAct agent with LLM, loads base tools + MCP tools + RAG tools
- **SessionManager**: 会话状态、记忆管理、文件上下文
- **Channel adapters**: IM 平台接入（飞书、企业微信）

## Directory Structure

### Backend (`soma/`)

| 目录 | 职责                                                 |
|------|----------------------------------------------------|
| `core/agent/` | DeepAgent 实现，LLM 初始化，工具加载                          |
| `core/chat/` | ChatService、SessionManager、MemoryManager           |
| `core/skill/` | 技能系统，从 `workspace/.soma/skills/` 加载                |
| `core/tool/` | 内置工具：file_read/write/edit、doc_parser、web_search 等  |
| `core/rag/` | RAG 知识库：chunker、embedding、vector_store、rag_service |
| `core/websocket/` | WebSocket 流式响应和文件上传                                |
| `channel/` | IM 通道适配器（飞书、企业微信）                                  |
| `service/` | 数据库、Elasticsearch 服务                               |
| `web/routers/` | FastAPI 路由                                         |
| `config/` | 配置和日志                                              |

### Frontend (`webui/`)

- `src/components/`: Vue 组件（ChatWindow、KnowledgeBase 等）
- `src/utils/api.js`: 所有后端 API 调用

### Workspace (`workspace/`)

- `skills/`: 技能目录，每个子目录含 `SKILL.md` + 可选 `references/`、`scripts/`
- `uploads/`: 用户上传的文件

## Key Configuration (`.env`)

| 变量 | 说明 |
|------|------|
| `OPENAI_API_KEY` | LLM 访问密钥 |
| `LLM_MODEL`, `LLM_MODEL_PROVIDER` | 模型配置 |
| `CONTEXT_STRATEGY` | 记忆压缩策略 |

## Tool System

- **Base tools**: `file_read`, `file_write`, `file_edit`, `grep`, `bash`, `doc_parser`, `web_fetch`, `web_search`, `search_data`
- **RAG tools**: `rag_search`, `rag_ingest`（自动从知识库检索）
- **MCP tools**: 来自 `MCP_SERVER_URL`（可选）

## Key Singletons

| 单例 | 路径 | 职责 |
|------|------|------|
| `agent_manager` | `core/agent/agent_manager.py` | 共享 DeepAgent 实例 |
| `chat_service` | `core/chat/chat_service.py` | HTTP 聊天请求 |
| `session_manager` | `core/chat/session_manager.py` | 会话+记忆+文件上下文 |
| `websocket_service` | `core/websocket/websocket_service.py` | WebSocket 流式响应和文件上传 |
| `rag_service` | `service/rag_service.py` | 知识库 CRUD + 检索 |
| `rag_embedding_service` | `service/rag_embedding_service.py` | 向量化服务 |
| `channel_router` | `channel/router.py` | IM 消息路由到 SessionManager |
| `channel_manager` | `channel/channel_manager.py` | IM 通道生命周期管理 |

## IM Channel Integration

Soma 支持通过适配器模式接入 IM 平台（飞书、企业微信）。

**数据流**: IM Platform → FeishuClient/WeComClient → ChannelRouter → SessionManager → DeepAgent → AI 回复

**ChannelManager 生命周期**:
1. 启动时从数据库加载 `enabled=1` 的通道，启动长连接
2. 运行时通过 Web UI 动态启用/停用/删除通道
3. 关闭时停止所有适配器

## RAG Knowledge Base

### Overview

知识库系统支持上传 PDF/Word 文档，语义检索后增强 AI 回答。

**流程**: 上传文档 → doc_parser 解析为 Markdown → chunker 分块 → embedding 向量化 → sqlite-vec 存储 → 检索

### Chunking Strategy

`soma/core/rag/chunker.py` 实现语义分块：

1. 按 `## H2` 二级标题分割成最小语义单元
2. 标题和其内容作为整体保留
3. 表格保持完整性，不跨块分割
4. chunk 大小不超过 `chunk_size * 1.1`
5. 小于 80 字符的块合并到前一个

**推荐配置**: `chunk_size=300`, `chunk_overlap=50`

### Embedding

中文文档使用 `bge-base-zh`（768维），英文使用 `all-MiniLM-L6-v2`（384维）

## API Response Format

All REST API responses follow this format:

```json
{
  "code": "200",        // String: "200" = success, other = failure
  "message": "success", // Human-readable message
  "data": { ... }       // Response data (null on failure)
}
```