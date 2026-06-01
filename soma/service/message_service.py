# service/message_service.py
from datetime import datetime
from typing import List, Dict, Optional, Any
from soma.config.logging_config import get_logger
from soma.model.db_model import SessionModel, MessageModel
from soma.service.database_manager import DatabaseManager
from soma.utils.message_handler import MessageHandler

logger = get_logger(__name__)


class MessageService:
    """消息服务 - 负责消息轮次的操作"""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    def save_round_message(self, session_id: str,
                           user_id: str,
                           user_message: str,
                           ai_message: str,
                           message_chain: List[Any],
                           round_number: int,
                           meta_data: Optional[Dict] = None) -> Optional[int]:
        """
        保存一次完整的对话轮次
        """
        session = self.db_manager.get_session()
        try:
            # 确保会话存在
            db_session = session.query(SessionModel).filter(
                SessionModel.session_id == session_id
            ).first()

            if not db_session:
                db_session = SessionModel(
                    session_id=session_id,
                    user_id=user_id,
                    title=f"会话_{session_id[:8]}"
                )
                session.add(db_session)
                session.flush()

            # 使用序列化器转换消息链
            message_chain_json = MessageHandler.serialize(message_chain)

            # 创建消息轮次记录
            message_round = MessageModel(
                session_id=session_id,
                user_message=user_message,
                ai_message=ai_message,
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
            logger.error(f"保存对话轮次失败: {str(e)}", exc_info=True)
            return None
        finally:
            session.close()

    def load_messages(self, session_id: str,
                      limit: int = None,
                      offset: int = None,
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

            if limit and offset:
                rounds = query.limit(limit).offset(offset).all()
            else:
                rounds = query.all()

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
        保存完整的消息流：AIMessage (可带 tool_calls) 和 ToolMessage
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
                # 保存 tool_calls（关键！）
                if hasattr(msg, 'tool_calls') and msg.tool_calls:
                    # 清理 tool_calls 确保可序列化
                    cleaned_calls = []
                    for tc in msg.tool_calls:
                        cleaned_calls.append({
                            'name': tc.get('name', ''),
                            'args': tc.get('args', {}),
                            'id': tc.get('id', '')
                        })
                    msg_data['tool_calls'] = cleaned_calls
                serialized.append(msg_data)

            elif isinstance(msg, ToolMessage):
                msg_data = {
                    'type': 'tool',
                    'content': msg.content,
                    'tool_call_id': msg.tool_call_id
                }
                if hasattr(msg, 'name') and msg.name:
                    msg_data['name'] = msg.name
                serialized.append(msg_data)

        return serialized
