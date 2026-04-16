# web/dependencies.py
from typing import Optional
from fastapi import Request
from core.chat.conversation_manager import ConversationManager
from core.agent.agent_manager import agent_manager


async def get_conversation_manager(request: Request, conversation_id: Optional[str] = None,
                                   user_id: Optional[str] = None):
    """
    依赖注入：创建新的 ConversationManager 实例

    注意：每个请求/会话应该有自己的 ConversationManager 实例
    """
    manager = ConversationManager(conversation_id=conversation_id, user_id=user_id)
    await manager.initialize(conversation_id=conversation_id, user_id=user_id)
    return manager


async def get_agent_manager(request: Request):
    """依赖注入：获取全局 AgentManager 实例"""
    return agent_manager
