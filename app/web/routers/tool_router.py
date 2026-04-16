# web/routers/tool_router.py
from dataclasses import dataclass, field
from typing import List, Dict, Any
from fastapi import APIRouter
from common.response import success_response, fail_response
from core.agent.agent_manager import agent_manager
from config.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/tool", tags=["tool"])


@dataclass
class ToolInfo:
    """工具信息模型"""
    name: str
    description: str
    is_high_risk: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "description": self.description,
            "is_high_risk": self.is_high_risk
        }


@dataclass
class ToolsResponse:
    """工具列表响应模型"""
    tools: List[ToolInfo] = field(default_factory=list)
    total: int = 0

    def __post_init__(self):
        self.total = len(self.tools)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "tools": [tool.to_dict() for tool in self.tools],
            "total": self.total
        }

    @classmethod
    def from_tool_list(cls, tools: List[Dict[str, Any]]) -> "ToolsResponse":
        """从工具列表创建响应"""
        tool_infos = []
        for tool in tools:
            tool_infos.append(ToolInfo(
                name=tool.get("name", ""),
                description=tool.get("description", "No description"),
                is_high_risk=tool.get("is_high_risk", False)
            ))
        return cls(tools=tool_infos)


@router.get("/list")
async def list_tools():
    """列出可用的工具"""
    try:
        agent_initialized = agent_manager.is_initialized()
        if not agent_initialized:
            logger.warning("Agent未初始化，无法获取工具列表")
            return fail_response(
                data={"tools": [], "total": 0},
                message="Agent未初始化"
            )

        tools_info = agent_manager.get_tools_info()
        logger.info(f"获取到 {len(tools_info)} 个工具")

        response = ToolsResponse.from_tool_list(tools_info)

        return success_response(
            data=response.to_dict(),
            message="获取工具列表成功"
        )

    except Exception as e:
        logger.error(f"获取工具列表失败: {str(e)}")
        return fail_response(
            data={"tools": [], "total": 0},
            message=f"获取工具列表失败: {str(e)}"
        )


@router.get("/{tool_name}")
async def get_tool(tool_name: str):
    """获取单个工具信息"""
    try:
        agent_initialized = agent_manager.is_initialized()
        if not agent_initialized:
            logger.warning("Agent未初始化，无法获取工具信息")
            return fail_response(message="Agent未初始化")

        tools_info = agent_manager.get_tools_info()
        tool = next((t for t in tools_info if t['name'] == tool_name), None)

        if not tool:
            logger.warning(f"工具 {tool_name} 不存在")
            return fail_response(message=f"工具 {tool_name} 不存在")

        # 创建ToolInfo对象
        tool_info = ToolInfo(
            name=tool['name'],
            description=tool.get('description', 'No description'),
            is_high_risk=tool.get('is_high_risk', False)
        )

        logger.info(f"成功获取工具信息: {tool_name}")
        return success_response(
            data=tool_info.to_dict(),
            message="获取工具信息成功"
        )

    except Exception as e:
        logger.error(f"获取工具信息失败: {str(e)}")
        return fail_response(message=f"获取工具信息失败: {str(e)}")
