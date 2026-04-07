from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime


@dataclass
class ChatMessage:
    """聊天消息模型"""
    role: str
    content: str
    timestamp: Optional[str] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp
        }


@dataclass
class ChatRequest:
    """聊天请求模型"""
    message: str
    conversation_id: Optional[str] = None
    stream: bool = False

    def __post_init__(self):
        if not self.message or not self.message.strip():
            raise ValueError("消息不能为空")
        if len(self.message) > 10000:
            raise ValueError("消息过长，最大长度10000字符")
        self.message = self.message.strip()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "message": self.message,
            "conversation_id": self.conversation_id,
            "stream": self.stream
        }


@dataclass
class ChatResponse:
    """聊天响应模型"""
    response: Any  # 改为 Any 类型，可以接受字符串或对象
    conversation_id: Optional[str] = None
    tools_used: List[str] = field(default_factory=list)
    intermediate_steps: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "response": self.response,
            "conversation_id": self.conversation_id,
            "tools_used": self.tools_used,
            "intermediate_steps": self.intermediate_steps
        }
