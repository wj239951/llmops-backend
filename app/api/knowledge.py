# 知识库文档 API 路由。
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.knowledge import KnowledgeCreate, KnowledgeOut, KnowledgeUpdate
from app.services.rag_service import RAGService

router = APIRouter(prefix="/knowledge", tags=["Knowledge"])
service = RAGService()

@router.post("", response_model=KnowledgeOut)
def create_document(data: KnowledgeCreate, db: Session = Depends(get_db)):
    return service.add_document(db, data.title, data.content, data.source)

@router.get("", response_model=list[KnowledgeOut])
def list_documents(db: Session = Depends(get_db)):
    return service.list_documents(db)

@router.put("/{knowledge_id}", response_model=KnowledgeOut)
def update_document(knowledge_id: int, data: KnowledgeUpdate, db: Session = Depends(get_db)):
    return service.update_document(db, knowledge_id, data.title, data.content, data.source)
@router.delete("/{knowledge_id}") #删除操作没有实体返回，故不使用 response_model
def delete_document(knowledge_id: int, db: Session = Depends(get_db)):
    return service.delete_document(db, knowledge_id)
