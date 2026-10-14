# 知识库文档新增、返回数据结构。
from datetime import datetime
from pydantic import BaseModel, ConfigDict

class KnowledgeCreate(BaseModel):
    title: str
    content: str
    source: str | None = None

class KnowledgeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    content: str
    source: str | None = None
    created_at: datetime

class KnowledgeUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    source: str | None = None