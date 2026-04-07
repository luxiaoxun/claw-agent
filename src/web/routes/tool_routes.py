from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import JSONResponse
from core.models.responses import ToolsResponse, ToolInfo
from web.dependencies import get_conversation_manager
from config.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/tools", tags=["tools"])


@router.get("/list")
async def list_tools(conversation_manager=Depends(get_conversation_manager)):
    """列出可用的工具"""
    try:
        # 关键修改1：通过依赖注入获取conversation_manager
        if not conversation_manager:
            raise HTTPException(status_code=503, detail="Agent未初始化")

        tools_info = conversation_manager.get_tools_info()

        # 使用工厂方法创建响应
        response = ToolsResponse.from_tool_list(tools_info)

        # 关键修改2：直接返回字典
        return response.to_dict()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取工具列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"内部错误: {str(e)}")


@router.get("/{tool_name}")
async def get_tool(
        tool_name: str,
        conversation_manager=Depends(get_conversation_manager)
):
    """获取单个工具信息"""
    try:
        # 关键修改3：通过依赖注入获取conversation_manager
        if not conversation_manager:
            raise HTTPException(status_code=503, detail="Agent未初始化")

        tools_info = conversation_manager.get_tools_info()
        tool = next((t for t in tools_info if t['name'] == tool_name), None)

        if not tool:
            raise HTTPException(status_code=404, detail=f"工具 {tool_name} 不存在")

        # 创建ToolInfo对象
        tool_info = ToolInfo(
            name=tool['name'],
            description=tool['description'],
            is_high_risk=tool.get('is_high_risk', False)
        )

        # 关键修改4：直接返回字典
        return tool_info.to_dict()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取工具信息失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"内部错误: {str(e)}")
