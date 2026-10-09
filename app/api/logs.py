# 运行日志接口，查询最近模型调用记录。
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.chat_log import ChatLog

router = APIRouter(prefix="/logs", tags=["Logs"])

@router.get("")
def list_logs(page: int = 1, page_size: int = 10, status: str | None = None, db: Session = Depends(get_db)):
    q = db.query(ChatLog)
    if status:  # 传了状态才过滤，不传返回全部
        q = q.filter(ChatLog.status == status)
    total = q.count()  # 总数要用带过滤条件的 q，分页条才准
    rows = (
        q.order_by(ChatLog.id.desc())
        .offset((page - 1) * page_size)  # 跳过前面几页
        .limit(page_size)                # 每页取几条
        .all()
    )
    return {
        "items": [
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
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }
