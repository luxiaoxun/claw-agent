# core/agent/agent_manager.py
from typing import Optional, List, Dict, Any
from core.agent.deep_agent import DeepAgent
from config.settings import WORKSPACE_DIR
from config.logging_config import get_logger

logger = get_logger(__name__)


class AgentManager:
    """
    Agent 管理器（单例模式）
    负责 DeepAgent 的创建、共享和生命周期管理
    """

    _instance: Optional['AgentManager'] = None
    _deep_agent: Optional[DeepAgent] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._deep_agent = None
        logger.info("AgentManager 单例创建")

    async def initialize(self):
        """初始化 Agent 管理器"""
        if self._deep_agent is not None:
            logger.info("Agent 已经初始化，跳过")
            return self

        try:
            logger.info("正在初始化 DeepAgent...")
            self._deep_agent = DeepAgent(WORKSPACE_DIR)
            await self._deep_agent.initialize()
            logger.info(f"DeepAgent 初始化成功，工具数: {len(self._deep_agent.base_tools + self._deep_agent.mcp_tools)}")
            return self
        except Exception as e:
            logger.error(f"DeepAgent 初始化失败: {str(e)}")
            raise

    def get_agent(self) -> DeepAgent:
        """获取共享的 DeepAgent 实例"""
        if self._deep_agent is None:
            raise RuntimeError("Agent 尚未初始化，请先调用 initialize()")
        return self._deep_agent

    async def close(self):
        """关闭 Agent 连接"""
        if self._deep_agent:
            await self._deep_agent.close()
            self._deep_agent = None
            logger.info("Agent 连接已关闭")

    def is_initialized(self) -> bool:
        """检查 Agent 是否已初始化"""
        return self._deep_agent is not None

    def get_tools_info(self) -> List[Dict]:
        """获取工具信息"""
        if self._deep_agent:
            return self._deep_agent.get_tools_info()
        return []


# 全局单例实例
agent_manager = AgentManager()
