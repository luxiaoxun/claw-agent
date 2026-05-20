# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Soma is a Python-based AI agent with a Vue 3 web UI. It provides chat-based interaction with LLM-powered agents that can use tools and skills to accomplish tasks.

## Development Commands

### Backend (Python/FastAPI)
```bash
# Install dependencies
uv sync

# Run the server
uv run python app/main.py

# Or with uvicorn directly
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 5000
```

### Frontend (Vue 3/Vite)
```bash
cd webui
npm install
npm run dev      # Development server at http://localhost:5173
npm run build    # Production build
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        前端 (Vue 3 + Vite)                       │
│  SessionSidebar ──── ChatWindow (WebSocket/HTTP)                │
│  SkillManagement                                            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        后端 (Python FastAPI)                     │
│                                                                 │
│  路由层 ──▶ ChatService ──▶ SessionManager ──▶ DeepAgent        │
│                                      ├── MemoryManager          │
│                                      └── FileManager            │
│                    │                      │                    │
│         ┌──────────┼──────────┐    ┌──────┴──────┐             │
│         ▼          ▼          ▼    ▼             ▼             │
│    AgentManager  Tools   SkillManager  Database  WebSocket       │
│                          (workspace/skills/)                   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              IM Channel Layer (channel/)                 │  │
│  │  FeishuClient / WeComClient (daemon thread)              │  │
│  │      ↓                                                    │  │
│  │  ChannelRouter → SessionManager → DeepAgent              │  │
│  │      ↓                                                    │  │
│  │  ChannelManager (管理 adapter 生命周期 from DB)           │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Backend (`app/`)
- **core/agent/**: ReAct agent using LangChain (`deep_agent.py`). Initializes LLM, loads tools (base + MCP).
- **core/chat/**: Chat orchestration - `chat_service.py` (HTTP), `session_manager.py` (会话), `chat_memory_manager.py` (历史).
- **core/skill/**: Skill system - `skill_manager.py` loads from `workspace/skills/`.
- **core/tool/**: Built-in tools - file operations, command execution, web search, Elasticsearch.
- **core/websocket/**: Streaming responses and file uploads.
- **channel/**: IM channel adapter layer (飞书等IM平台对接).
  - `base.py`: `IChannelAdapter` 抽象类、`NormalizedMessage`、`IMContext` 数据类
  - `channel_manager.py`: 从数据库加载配置，管理所有IM通道适配器生命周期
  - `router.py`: `ChannelRouter` 将 IM 消息路由到 SessionManager
  - `feishu/`: 飞书适配器实现 (`feishu_client.py`, `feishu_adapter.py`, `feishu_api.py`, `feishu_parser.py`)
  - `wecom/`: 企业微信适配器实现 (`wecom_client.py`, `wecom_adapter.py`, `wecom_parser.py`)
- **service/**: Database and Elasticsearch services.
- **web/routers/**: FastAPI routes (chat, sessions, skills, tools, im).
- **config/**: Settings from `.env`, logging.

### Frontend (`webui/`)
Vue 3 SPA with Vite. Communicates with backend via REST API (`/api/chat/message`) and WebSocket (`/api/chat/ws/message`).

### Tool System (`app/core/tool/`)
- **Base tools**: `file_read`, `file_write`, `file_edit`, `file_search`, `command_execute`, `doc_parser`, `web_fetch`, `web_search`, `search_data`
- **MCP tools**: Loaded from `MCP_SERVER_URL` (optional)

### Key Singletons
| 单例 | 路径 | 职责 |
|------|------|------|
| `agent_manager` | `core/agent/agent_manager.py` | 共享 DeepAgent 实例 |
| `chat_service` | `core/chat/chat_service.py` | HTTP 聊天请求 |
| `session_manager` | `core/chat/session_manager.py` | 会话+记忆+文件上下文 |
| `websocket_service` | `core/websocket/websocket_service.py` | WebSocket 连接 |
| `skill_manager` | `core/skill/skill_manager.py` | 技能加载 |
| `database_service` | `service/database_service.py` | 数据库访问 |
| `channel_router` | `app/channel/router.py` | IM消息路由到SessionManager |
| `channel_manager` | `app/channel/channel_manager.py` | IM通道生命周期管理 |

### Workspace (`workspace/`)
- `skills/`: Each subdirectory is a skill with `SKILL.md` + optional `references/`, `scripts/`, `assets/` directories.
- `uploads/`: User-uploaded files.

## Key Configuration (`.env`)
- `OPENAI_API_KEY`: Required for LLM access
- `LLM_MODEL`, `LLM_MODEL_PROVIDER`, `OPENAI_BASE_URL`: Model configuration
- `ES_HOSTS`, `ES_USERNAME`, `ES_PASSWORD`: Elasticsearch connection for data search
- `USE_MCP`, `MCP_SERVER_URL`: Optional MCP server for additional tools
- `CONTEXT_STRATEGY`: Memory compression strategy (`round`, `token`, `message_count`)

## IM Channel Integration

Soma supports receiving and responding to messages from IM platforms via an adapter pattern. Configuration is stored in SQLite database and managed via Web UI.

### Architecture

```
IM Platform ←WS long-poll→ FeishuClient / WeComClient (daemon thread)
                              ↓
                         FeishuParser / WeComParser → NormalizedMessage
                              ↓
                         ChannelRouter → SessionManager → DeepAgent
                              ↓
                         FeishuAPI.reply_text() / WeComAdapter.reply_to_message() → IM Platform
```

### Session Model

| Chat Type | Session ID | Description |
|-----------|------------|-------------|
| **P2P** | `hash(platform + user_id + chat_id)` | Each user in each chat gets unique session |
| **Group** | `hash(platform + chat_id)` | All group members share one session |

### Database Schema

**tb_channel_config** - IM通道配置表
| Column | Type | Description |
|--------|------|-------------|
| id | Integer (PK) | 自增ID |
| platform | String(50) | 平台类型：`feishu` / `wecom` |
| name | String(255) | 用户自定义名称 |
| enabled | Integer | 0=停用, 1=启用 |
| config | JSON | 平台凭证（app_id/app_secret 等） |
| description | Text | 描述 |
| create_time | DateTime | 创建时间 |
| update_time | DateTime | 更新时间 |

**tb_channel_status** - IM通道运行时状态表
| Column | Type | Description |
|--------|------|-------------|
| id | Integer (PK) | 自增ID |
| channel_id | Integer (FK) | 关联 tb_channel_config.id |
| status | String(50) | `connected` / `disconnected` / `error` |
| last_heartbeat | DateTime | 最后心跳时间 |
| error_message | Text | 错误信息 |
| update_time | DateTime | 更新时间 |

### Key Components

| File | Purpose |
|------|---------|
| `channel/base.py` | `IChannelAdapter` 抽象类、`NormalizedMessage`、`IMContext` 数据类 |
| `channel/channel_manager.py` | 从数据库加载配置，管理所有IM通道适配器生命周期 |
| `channel/router.py` | 将 NormalizedMessage 路由到 SessionManager，发送AI响应 |
| `channel/feishu/feishu_client.py` | `lark.ws.Client` 长连接，接收飞书事件（daemon thread 避免 event loop 冲突） |
| `channel/feishu/feishu_adapter.py` | `IChannelAdapter` 实现，配置从数据库或环境变量读取 |
| `channel/feishu/feishu_parser.py` | 解析 `P2ImMessageReceiveV1` → `NormalizedMessage` |
| `channel/feishu/feishu_api.py` | REST API 发送消息：`message.create` / `message.reply` |
| `channel/wecom/wecom_client.py` | `aibot.WSClient` 长连接，接收企业微信事件 |
| `channel/wecom/wecom_adapter.py` | 企业微信 `IChannelAdapter` 实现 |
| `channel/wecom/wecom_parser.py` | 解析企业微信帧 → `NormalizedMessage` |
| `web/routers/channel_router.py` | 通道 CRUD API（创建/更新/删除/启用/停用） |

### Web UI Channel Management

导航菜单「消息通道」→ `ChannelManagement.vue`
- 列表展示所有通道（平台/名称/状态/连接状态/创建时间）
- 创建/编辑通道：选择平台（飞书/企业微信），填写配置信息
- 启用/停用通道：通过开关直接控制，实时通知 ChannelManager
- 删除通道：先停止适配器，再删除数据库记录

### ChannelManager Lifecycle

1. **启动时**：`main.py` lifespan 调用 `channel_manager.start_all()`
   - 从数据库加载所有 `enabled=1` 的通道
   - 根据 `platform` 创建对应适配器（FeishuAdapter / WeComAdapter）
   - 调用 `adapter.start_with_config(config)` 启动长连接
   - 更新数据库状态为 `connected`

2. **运行时**：通过 Web UI 或 API 动态管理
   - **启用通道**：`channel_router.enable_channel()` → `cm.start_channel()`
   - **停用通道**：`channel_router.disable_channel()` → `cm.stop_channel()`
   - **删除通道**：先 `cm.stop_channel()`，再删除数据库记录

3. **关闭时**：`main.py` lifespan 调用 `channel_manager.stop_all()`
   - 停止所有适配器，清理长连接

### WeCom Event Data Structure (aibot SDK)

```
frame.body:
  chatid       → chat_id (群聊时)
  chattype     → 'single' / 'group'
  content      → 消息内容（文本）
  from.userid  → user_id
  msgid        → message_id
  msgtype      → 'text'
  robotagentid → bot_id
```

### Feishu Event Data Structure (lark-oapi 1.6.x)

```
P2ImMessageReceiveV1
  .event.message.chat_id        → chat_id
  .event.message.message_id     → message_id (用于回复)
  .event.message.message_type   → text/post/image等
  .event.message.content        → JSON string
  .event.message.chat_type      → p2p/group
  .event.sender.sender_id.open_id → user_id
```

## API Endpoints
- `POST /api/chat/message`: Send chat message (HTTP)
- `WebSocket /api/chat/ws/message`: Streaming chat with file upload support
- `GET /api/docs`: Swagger documentation at http://127.0.0.1:5000/docs

## API Response Format
All REST API responses follow this format:
```json
{
  "code": "200",        // String: "200" = success, other = failure
  "message": "success",  // Human-readable message
  "data": { ... }        // Response data (null on failure)
}
```
