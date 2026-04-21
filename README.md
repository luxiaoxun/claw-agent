# Claw Agent

一个简单的AI Agent

## 功能特性

### 内置工具
- 文件读写、编辑、查找
- DOC/PDF文档转换
- 命令执行
- 网页获取

### 内置Skill（样例）
- 告警解读：通过AI解读分析告警日志
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
cd claw-agent

# 安装依赖
uv sync

# 配置环境变量
cp .env.example .env
# 编辑.env文件，填入你的配置

# 运行项目
uv run python app/main.py
```

### API docs
http://127.0.0.1:5000/docs