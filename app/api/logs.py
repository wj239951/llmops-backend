# 运行日志接口，查询最近模型调用记录。
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.chat_log import ChatLog

router = APIRouter(prefix="/logs", tags=["Logs"])

@router.get("")
def list_logs(db: Session = Depends(get_db)):
    rows = db.query(ChatLog).order_by(ChatLog.id.desc()).limit(100).all()
    return [
        {
            "id": row.id,
            "user_input": row.user_input,
            "assistant_output": row.assistant_output,
            "model_provider": row.model_provider,
            "model_name": row.model_name,
            "prompt_name": row.prompt_name,
            "total_tokens": row.total_tokens,
            "latency_ms": row.latency_ms,
            "status": row.status,
            "error_message": row.error_message,
            "created_at": row.created_at,
        }
        for row in rows
    ]
