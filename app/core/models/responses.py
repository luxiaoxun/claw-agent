from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class HealthResponse:
    """健康检查响应模型"""
    status: str
    agent_initialized: bool
    tools_loaded: int = 0
    version: str = "1.0.0"

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "status": self.status,
            "agent_initialized": self.agent_initialized,
            "tools_loaded": self.tools_loaded,
            "version": self.version
        }

    @classmethod
    def healthy(cls, tools_loaded: int, version: str = "1.0.0") -> "HealthResponse":
        """创建健康状态响应"""
        return cls(
            status="healthy",
            agent_initialized=True,
            tools_loaded=tools_loaded,
            version=version
        )

    @classmethod
    def initializing(cls, version: str = "1.0.0") -> "HealthResponse":
        """创建初始化中状态响应"""
        return cls(
            status="initializing",
            agent_initialized=False,
            tools_loaded=0,
            version=version
        )


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
            "tool": [tool.to_dict() for tool in self.tools],
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


@dataclass
class ErrorResponse:
    """错误响应模型"""
    error: str
    code: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = {"error": self.error}
        if self.code:
            result["code"] = self.code
        if self.details:
            result["details"] = self.details
        return result

    @classmethod
    def bad_request(cls, message: str, details: Optional[Dict] = None) -> "ErrorResponse":
        """创建400错误响应"""
        return cls(error=message, code="BAD_REQUEST", details=details)

    @classmethod
    def not_found(cls, message: str) -> "ErrorResponse":
        """创建404错误响应"""
        return cls(error=message, code="NOT_FOUND")

    @classmethod
    def server_error(cls, message: str = "服务器内部错误") -> "ErrorResponse":
        """创建500错误响应"""
        return cls(error=message, code="INTERNAL_ERROR")