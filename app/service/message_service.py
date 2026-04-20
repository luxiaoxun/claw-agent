# service/message_service.py
from datetime import datetime
from typing import List, Dict, Optional, Any
from config.logging_config import get_logger
from core.model.db_model import SessionModel, MessageModel
from service.database_manager import DatabaseManager

logger = get_logger(__name__)


class MessageService:
    """消息服务 - 负责消息轮次的操作"""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    def save_round_message(self, session_id: str,
                           user_message: str,
                           ai_response: str,
                           message_chain: List[Any],
                           round_number: int,
                           meta_data: Optional[Dict] = None) -> Optional[int]:
        """
        保存一次完整的对话轮次

        Args:
            session_id: 会话ID
            user_message: 用户消息
            ai_response: AI响应
            message_chain: 完整的消息链（LangChain消息对象列表）
            round_number: 轮次序号
            meta_data: 元数据

        Returns:
            保存的记录ID，失败返回None
        """
        session = self.db_manager.get_session()
        try:
            # 确保会话存在
            db_session = session.query(SessionModel).filter(
                SessionModel.session_id == session_id
            ).first()

            if not db_session:
                # 自动创建会话
                db_session = SessionModel(
                    session_id=session_id,
                    title=f"会话_{session_id[:8]}"
                )
                session.add(db_session)
                session.flush()

            # 转换消息链为可存储的JSON格式
            message_chain_json = self._serialize_message_chain(message_chain)

            # 创建消息轮次记录
            message_round = MessageModel(
                session_id=session_id,
                user_message=user_message,
                ai_response=ai_response,
                message_chain=message_chain_json,
                round_number=round_number,
                meta_data=meta_data,
                create_time=datetime.now()
            )
            session.add(message_round)

            # 更新会话的更新时间
            db_session.update_time = datetime.now()

            session.commit()
            logger.info(f"成功保存对话轮次 {round_number} 到会话 {session_id}")
            return message_round.id

        except Exception as e:
            session.rollback()
            logger.error(f"保存对话轮次失败: {str(e)}")
            return None
        finally:
            session.close()

    def load_messages(self, session_id: str,
                      limit: int = 50,
                      offset: int = 0,
                      order_desc: bool = False) -> List[Dict]:
        """
        加载会话的对话轮次

        Args:
            session_id: 会话ID
            limit: 返回记录数量限制
            offset: 偏移量
            order_desc: 是否按时间倒序（最新的在前）

        Returns:
            对话轮次列表
        """
        session = self.db_manager.get_session()
        try:
            query = session.query(MessageModel).filter(
                MessageModel.session_id == session_id
            )

            # 根据 order_desc 参数决定排序方式
            if order_desc:
                query = query.order_by(MessageModel.create_time.desc())
            else:
                query = query.order_by(MessageModel.create_time.asc())

            rounds = query.limit(limit).offset(offset).all()

            return [round_.to_dict() for round_ in rounds]

        except Exception as e:
            logger.error(f"加载对话轮次失败: {str(e)}")
            return []
        finally:
            session.close()

    def get_message_rounds_count(self, session_id: str) -> int:
        """获取会话的消息轮次总数"""
        session = self.db_manager.get_session()
        try:
            count = session.query(MessageModel).filter(
                MessageModel.session_id == session_id
            ).count()
            return count
        except Exception as e:
            logger.error(f"获取消息轮次数量失败: {str(e)}")
            return 0
        finally:
            session.close()

    def _serialize_message_chain(self, messages: List[Any]) -> List[Dict]:
        """
        将 LangChain 消息链序列化为 JSON 可存储格式
        """
        from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

        serialized = []

        for msg in messages:
            if isinstance(msg, HumanMessage):
                # HumanMessage 不保存到消息链，因为已经在 user_message 字段中
                continue
            elif isinstance(msg, AIMessage):
                msg_data = {
                    'type': 'ai',
                    'content': msg.content,
                }
                if hasattr(msg, 'tool_calls') and msg.tool_calls:
                    msg_data['tool_calls'] = msg.tool_calls
                serialized.append(msg_data)
            elif isinstance(msg, ToolMessage):
                serialized.append({
                    'type': 'tool',
                    'content': msg.content,
                    'tool_call_id': msg.tool_call_id
                })

        return serialized
