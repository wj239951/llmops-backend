# 知识库文档新增、返回数据结构。
from datetime import datetime
from pydantic import BaseModel

class KnowledgeCreate(BaseModel):
    title: str
    content: str
    source: str | None = None

class KnowledgeOut(BaseModel):
    id: int
    title: str
    content: str
    source: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True
