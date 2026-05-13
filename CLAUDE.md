# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Claw Agent is a Python-based AI agent with a Vue 3 web UI. It provides chat-based interaction with LLM-powered agents that can use tools and skills to accomplish tasks.

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

### Backend (`app/`)
- **core/agent/**: ReAct agent implementation using LangChain (`deep_agent.py`). Initializes LLM, loads tools (base + MCP), handles message processing (streaming and non-streaming).
- **core/chat/**: Chat orchestration - `chat_service.py` handles HTTP requests, `session_manager.py` manages individual chat sessions, `chat_memory_manager.py` handles history with configurable context strategies (round-based, token-based, message-count-based).
- **core/skill/**: Skill system - `skill_manager.py` loads skills from `workspace/skills/` directory (each skill has a `SKILL.md` with frontmatter containing name/description).
- **core/tool/**: Built-in tools - file operations (read/write/edit/search), command execution, document parsing, web search/fetch, data search via Elasticsearch.
- **core/websocket/**: WebSocket support for streaming responses and file uploads.
- **service/**: Database and Elasticsearch query services.
- **web/routers/**: FastAPI route handlers for chat, sessions, skills, tools.
- **config/**: Settings via `settings.py` (reads from `.env`), logging configuration.

### Frontend (`webui/`)
Vue 3 SPA with Vite. Communicates with backend via REST API (`/api/chat/message`) and WebSocket (`/api/chat/ws/message`).

### Tool System (`app/core/tool/`)
Base tools: `file_read`, `file_write`, `file_edit`, `file_search`, `command_execute`, `doc_parser`, `web_fetch`, `web_search`, `search_data`. MCP tools loaded optionally from `MCP_SERVER_URL`.

### Context Strategies (`app/core/chat/memory/strategy/`)
Three configurable strategies via `CONTEXT_STRATEGY`: `round` (last N conversation rounds), `token` (last N tokens), `message_count` (last N messages). Factory in `context_strategy_factory.py`.

### Key Singletons
- `agent_manager` (`app/core/agent/agent_manager.py`): Shared DeepAgent instance
- `database_service` (`app/service/database_service.py`): Database and session/message services
- `websocket_service` (`app/core/websocket/websocket_service.py`): WebSocket connection management
- `skill_manager`: Loaded in `app/main.py` lifespan, accessed via `app.state.skill_manager`

### Workspace (`workspace/`)
- `skills/`: Each subdirectory is a skill with `SKILL.md` + optional `references/`, `scripts/`, `assets/` directories.
- `uploads/`: User-uploaded files.

## Key Configuration (`.env`)
- `OPENAI_API_KEY`: Required for LLM access
- `LLM_MODEL`, `LLM_MODEL_PROVIDER`, `OPENAI_BASE_URL`: Model configuration
- `ES_HOSTS`, `ES_USERNAME`, `ES_PASSWORD`: Elasticsearch connection for data search
- `USE_MCP`, `MCP_SERVER_URL`: Optional MCP server for additional tools
- `CONTEXT_STRATEGY`: Memory compression strategy (`round`, `token`, `message_count`)

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
