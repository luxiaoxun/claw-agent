# Soma

## Security Operations Management Agent

Soma is a Python-based AI agent with a Vue 3 web UI. It provides chat-based interaction with LLM-powered agents that can use tools and skills to accomplish tasks.

## 功能特性
- 聊天Chat：支持流式会话、文件传输
- 会话管理：多用户多session会话
- Contxt：上下文memory压缩
- Skill管理：动态加载Skill
- 消息通道：对接飞书、企业微信机器人
- WebUI：浏览器Web界面

### 内置工具

| 工具 | 用途 | 示例 |
|------|------|------|
| **skill_load** | 加载技能 | `{"skill_name": "alert_analysis"}` |
| **file_read** | 读取文件（文本/图片/PDF） | `{"path": "/workspace/file.txt"}` |
| **file_write** | 写入文件 | `{"path": "output.txt", "content": "..."}` |
| **file_edit** | 编辑文件（字符串替换） | `{"filePath": "x.py", "oldString": "a", "newString": "b"}` |
| **glob** | 文件名模式搜索 | `{"pattern": "**/*.py"}` |
| **grep** | 内容正则搜索 | `{"pattern": "TODO", "include": "*.py"}` |
| **bash** | 执行命令/代码 | `{"command": "python script.py"}` |
| **web_fetch** | 获取URL内容 | `{"url": "https://example.com"}` |
| **web_search** | 网页搜索 | `{"query": "AI news", "max_results": 10}` |
| **doc_parser** | PDF/DOCX → Markdown | `{"input_path": "doc.pdf", "output_path": "out.md"}` |
| **csv_read** | 读取CSV文件 | `{"path": "data.csv"}` |
| **csv_write** | 写入CSV文件 | `{"path": "out.csv", "data": [...]}` |
| **csv_filter** | 筛选CSV行 | `{"path": "data.csv", "filter_expr": "age > 18"}` |
| **api_request** | HTTP API调用 | `{"url": "https://api.com", "method": "GET"}` |
| **data_search** | Elasticsearch查询 | `{"indexName": "event", "query": "severity>=3"}` |

### 内置Skill（样例）
- 告警解读：AI解读分析告警日志
- 网站分析：对网站进行安全性分析
- 数据查询：通过自然语言查询Elasticsearch
- 报告生成：通过Skill生成报告

## 快速开始

### 环境要求

- Python 3.12+
- OpenAI API Key
- MCP服务器（可选）

### 安装

```bash
# 克隆项目
git clone <repository-url>
cd soma

# 安装依赖
uv sync

# 配置环境变量
cp .env.example .env
# 编辑.env文件，填入你的配置

# 运行后端
uv run uvicorn soma.main:app --host 0.0.0.0 --port 5000
```

### API docs
http://127.0.0.1:5000/docs

### Web UI
```bash
npm run dev
```
http://localhost:5173/