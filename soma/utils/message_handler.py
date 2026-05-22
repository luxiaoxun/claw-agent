"""
消息序列化工具类
负责 LangChain 消息对象与 JSON 格式之间的转换
"""
from typing import List, Dict, Any, Optional
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
from soma.config.logging_config import get_logger

logger = get_logger(__name__)


class MessageHandler:
    """
    消息序列化器
    将 LangChain 消息对象序列化为 JSON 可存储格式，以及反向反序列化
    """

    @staticmethod
    def serialize(messages: List[BaseMessage]) -> List[Dict]:
        """
        将 LangChain 消息链序列化为 JSON 可存储格式
        保存完整的消息流：AIMessage (可带 tool_calls) 和 ToolMessage

        Args:
            messages: LangChain 消息对象列表

        Returns:
            序列化后的字典列表，适合 JSON 存储
        """
        serialized = []

        for msg in messages:
            # HumanMessage 不保存到消息链，因为已经在 user_message 字段中
            if isinstance(msg, HumanMessage):
                continue

            elif isinstance(msg, AIMessage):
                msg_data = MessageHandler._serialize_ai_message(msg)
                serialized.append(msg_data)

            elif isinstance(msg, ToolMessage):
                msg_data = MessageHandler._serialize_tool_message(msg)
                serialized.append(msg_data)

            else:
                logger.warning(f"未知的消息类型: {type(msg).__name__}，跳过序列化")

        return serialized

    @staticmethod
    def deserialize(message_chain: List[Dict]) -> List[BaseMessage]:
        """
        将序列化的消息链反序列化为 LangChain 消息对象列表

        Args:
            message_chain: 序列化的消息链数据

        Returns:
            LangChain 消息对象列表
        """
        if not message_chain:
            return []

        messages = []

        for msg_data in message_chain:
            msg_type = msg_data.get('type')

            if msg_type == 'ai':
                msg = MessageHandler._deserialize_ai_message(msg_data)
                if msg:
                    messages.append(msg)

            elif msg_type == 'tool':
                msg = MessageHandler._deserialize_tool_message(msg_data)
                if msg:
                    messages.append(msg)

            else:
                logger.warning(f"未知的消息类型: {msg_type}，跳过反序列化")

        return messages

    @staticmethod
    def _serialize_ai_message(msg: AIMessage) -> Dict:
        """
        序列化 AIMessage 对象
        """
        msg_data = {
            'type': 'ai',
            'content': msg.content,
        }

        # 保存 tool_calls
        if hasattr(msg, 'tool_calls') and msg.tool_calls:
            cleaned_calls = []
            for tc in msg.tool_calls:
                cleaned_calls.append({
                    'name': tc.get('name', ''),
                    'args': tc.get('args', {}),
                    'id': tc.get('id', '')
                })
            msg_data['tool_calls'] = cleaned_calls

        return msg_data

    @staticmethod
    def _serialize_tool_message(msg: ToolMessage) -> Dict:
        """
        序列化 ToolMessage 对象
        """
        msg_data = {
            'type': 'tool',
            'content': msg.content,
            'tool_call_id': msg.tool_call_id
        }

        # 保存 name 属性
        if hasattr(msg, 'name') and msg.name:
            msg_data['name'] = msg.name

        return msg_data

    @staticmethod
    def _deserialize_ai_message(msg_data: Dict) -> AIMessage:
        """
        反序列化为 AIMessage 对象
        """
        ai_msg = AIMessage(content=msg_data.get('content', ''))

        # 恢复 tool_calls
        if msg_data.get('tool_calls'):
            tool_calls = []
            for tc in msg_data.get('tool_calls', []):
                tool_calls.append({
                    'name': tc.get('name', ''),
                    'args': tc.get('args', {}),
                    'id': tc.get('id', '')
                })
            ai_msg.tool_calls = tool_calls

        return ai_msg

    @staticmethod
    def _deserialize_tool_message(msg_data: Dict) -> ToolMessage:
        """
        反序列化为 ToolMessage 对象
        """
        tool_call_id = msg_data.get('tool_call_id', '')

        # 验证 tool_call_id
        if not tool_call_id:
            logger.warning(f"ToolMessage 缺少 tool_call_id，使用默认值")
            tool_call_id = f"unknown_{msg_data.get('name', 'tool')}"

        tool_msg = ToolMessage(
            content=msg_data.get('content', ''),
            tool_call_id=tool_call_id,
            name=msg_data.get('name', '')
        )

        return tool_msg

    @staticmethod
    def validate_message_chain(messages: List[BaseMessage]) -> bool:
        """
        验证消息链的有效性
        检查消息序列是否符合 LangGraph 要求

        Args:
            messages: 消息链

        Returns:
            是否有效
        """
        if not messages:
            return True

        for i, msg in enumerate(messages):
            # ToolMessage 必须跟在有对应 tool_call_id 的 AIMessage 之后
            if isinstance(msg, ToolMessage):
                # 检查前面的消息
                if i == 0:
                    logger.warning(f"ToolMessage 出现在消息链开头，位置 {i}")
                    return False

                # 查找对应的 AIMessage
                found = False
                for j in range(i - 1, -1, -1):
                    prev_msg = messages[j]
                    if isinstance(prev_msg, AIMessage):
                        if hasattr(prev_msg, 'tool_calls') and prev_msg.tool_calls:
                            for tc in prev_msg.tool_calls:
                                if tc.get('id') == msg.tool_call_id:
                                    found = True
                                    break
                        if found:
                            break

                if not found:
                    logger.warning(f"ToolMessage (tool_call_id={msg.tool_call_id}) 找不到对应的 AIMessage")
                    return False

        return True

    @staticmethod
    def extract_final_ai_response(messages: List[BaseMessage]) -> str:
        """
        从消息链中提取最终的 AI 响应内容

        Args:
            messages: 消息链

        Returns:
            AI 响应内容
        """
        # 从后往前找最后一个 AIMessage
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and msg.content:
                return msg.content

        return ""

    @staticmethod
    def build_ai_message(content_parts: List[str], tool_calls_dict: Dict) -> Optional[AIMessage]:
        """
        从内容片段和 tool_calls 字典构建 AIMessage

        Args:
            content_parts: 内容片段列表
            tool_calls_dict: tool_calls 字典 {id: {name, args, id}}

        Returns:
            AIMessage 或 None
        """
        content = ''.join(content_parts)

        # 过滤有效的 tool_calls
        valid_tool_calls = [
            tc for tc in tool_calls_dict.values()
            if tc.get('name') and tc.get('id')
        ]

        # 只有有内容或有效 tool_calls 时才创建
        if content or valid_tool_calls:
            return AIMessage(
                content=content,
                tool_calls=valid_tool_calls  # 直接传递列表，即使为空
            )

        return None
