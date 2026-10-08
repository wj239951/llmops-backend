# 会话管理接口：列表、新建、获取聊天记录。
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.conversation import Conversation
from app.models.chat_log import ChatLog

router = APIRouter(prefix="/conversations", tags=["Conversations"])

@router.get("")
def list_conversations(db: Session = Depends(get_db)):
    """获取所有会话，按更新时间倒序"""
    rows = db.query(Conversation).order_by(Conversation.updated_at.desc()).all()
    return [
        {
            "id": row.id,
            "title": row.title,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }
        for row in rows
    ]

@router.post("")
def create_conversation(db: Session = Depends(get_db)):
    """创建新会话"""
    import uuid
    new_id = str(uuid.uuid4())
    conv = Conversation(id=new_id, title="新会话")
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return {
        "id": conv.id,
        "title": conv.title,
        "created_at": conv.created_at,
        "updated_at": conv.updated_at,
    }

@router.get("/{conversation_id}/messages")
def get_messages(conversation_id: str, db: Session = Depends(get_db)):
    """获取某个会话的聊天记录"""
    logs = (
        db.query(ChatLog)
        .filter(ChatLog.conversation_id == conversation_id, ChatLog.status == "success")
        .order_by(ChatLog.created_at.asc())
        .all()
    )
    return [
        {
            "user_input": log.user_input,
            "assistant_output": log.assistant_output,
            "model_provider": log.model_provider,
            "model_name": log.model_name,
            "created_at": log.created_at,
        }
        for log in logs
    ]

@router.delete("/{conversation_id}")
def delete_conversation(conversation_id: str, db: Session = Depends(get_db)):
    """删除会话及其聊天记录"""
    db.query(ChatLog).filter(ChatLog.conversation_id == conversation_id).delete()
    db.query(Conversation).filter(Conversation.id == conversation_id).delete()
    db.commit()
    return {"deleted": conversation_id}
