# web/routers/agent_router.py
from fastapi import APIRouter, Depends
from soma.common.response import success_response, fail_response
from soma.config.logging_config import get_logger
from soma.core.agent.agent_manager import agent_manager

logger = get_logger(__name__)
router = APIRouter(prefix="/agent", tags=["agent"])


@router.get("/llm/config")
async def get_llm_config():
    """获取当前 LLM 配置"""
    try:
        config = agent_manager.agent.get_llm_config()
        return success_response(data=config)
    except Exception as e:
        logger.error(f"获取LLM配置失败: {str(e)}")
        return fail_response(message=f"获取LLM配置失败: {str(e)}")


@router.post("/llm/config")
async def update_llm_config(config: dict):
    """更新 LLM 配置并重建 Agent"""
    try:
        success = agent_manager.agent.update_llm_config(config)
        if success:
            return success_response(data=agent_manager.agent.get_llm_config())
        else:
            return fail_response(message="LLM配置不完整或更新失败")
    except Exception as e:
        logger.error(f"更新LLM配置失败: {str(e)}")
        return fail_response(message=f"更新LLM配置失败: {str(e)}")