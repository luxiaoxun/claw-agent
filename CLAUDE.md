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
│  │  FeishuClient (ws.Client) ──▶ ChannelRouter ──▶ Response │  │
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
  - `router.py`: `ChannelRouter` 将 IM 消息路由到 SessionManager
  - `feishu/`: 飞书适配器实现 (`feishu_client.py`, `feishu_adapter.py`, `feishu_api.py`, `feishu_parser.py`)
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

### Workspace (`workspace/`)
- `skills/`: Each subdirectory is a skill with `SKILL.md` + optional `references/`, `scripts/`, `assets/` directories.
- `uploads/`: User-uploaded files.

## Key Configuration (`.env`)
- `OPENAI_API_KEY`: Required for LLM access
- `LLM_MODEL`, `LLM_MODEL_PROVIDER`, `OPENAI_BASE_URL`: Model configuration
- `ES_HOSTS`, `ES_USERNAME`, `ES_PASSWORD`: Elasticsearch connection for data search
- `USE_MCP`, `MCP_SERVER_URL`: Optional MCP server for additional tools
- `CONTEXT_STRATEGY`: Memory compression strategy (`round`, `token`, `message_count`)
- `IM_ENABLED`: Enable IM channel adapter (true/false)
- `FEISHU_APP_ID`, `FEISHU_APP_SECRET`: Feishu bot credentials

## IM Channel Integration (飞书)

Soma supports receiving and responding to messages from IM platforms via an adapter pattern.

### Architecture

```
Feishu Server ←WS long-poll→ FeishuClient (daemon thread)
                              ↓
                         FeishuParser → NormalizedMessage
                              ↓
                         ChannelRouter → SessionManager → DeepAgent
                              ↓
                         FeishuAPI.reply_text() → Feishu Server
```

### Session Model

| Chat Type | Session ID | Description |
|-----------|------------|-------------|
| **P2P** | `hash(platform + user_id + chat_id)` | Each user in each chat gets unique session |
| **Group** | `hash(platform + chat_id)` | All group members share one session |

### Key Components

| File | Purpose |
|------|---------|
| `channel/base.py` | `IChannelAdapter`, `NormalizedMessage`, `IMContext` |
| `channel/router.py` | Routes normalized IM messages to SessionManager |
| `channel/feishu/feishu_client.py` | `lark.ws.Client` long-poll connection in daemon thread |
| `channel/feishu/feishu_adapter.py` | `IChannelAdapter` implementation, wires event to router |
| `channel/feishu/feishu_parser.py` | Parses `P2ImMessageReceiveV1` → `NormalizedMessage` |
| `channel/feishu/feishu_api.py` | REST API for `message.create` / `message.reply` |
| `web/routers/im_router.py` | IM status/config API endpoints |

### Startup Flow

1. `main.py` lifespan: if `IM_ENABLED=true`, create `FeishuAdapter` and call `start()`
2. `FeishuAdapter.start()` creates `FeishuClient` and starts `lark.ws.Client` in a **daemon thread** (avoids event loop conflict with FastAPI)
3. `FeishuClient` registers `EventDispatcherHandler` with `register_p2_im_message_receive_v1`
4. When a message arrives: `_on_p2_im_message_receive` → `FeishuParser.parse()` → `ChannelRouter.route_message()` → `SessionManager.process_message()` → AI response → `FeishuAPI.reply_text()`

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
