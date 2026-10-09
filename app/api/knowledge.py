# 知识库文档 API 路由。
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.knowledge import KnowledgeCreate, KnowledgeOut, KnowledgeUpdate
from app.services.rag_service import RAGService
from app.services.file_parser import parse_file

router = APIRouter(prefix="/knowledge", tags=["Knowledge"])
service = RAGService()

@router.post("", response_model=KnowledgeOut)
def create_document(data: KnowledgeCreate, db: Session = Depends(get_db)):
    return service.add_document(db, data.title, data.content, data.source)

@router.post("/upload", response_model=KnowledgeOut)
async def upload_file(
    file: UploadFile = File(...),
    title: str | None = None,
    db: Session = Depends(get_db)
):
    """上传文件，解析内容后存入知识库"""
    try:
        content = await parse_file(file)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件解析失败: {str(e)}")

    # 用文件名作为默认标题
    doc_title = title or file.filename
    return service.add_document(db, doc_title, content, source=file.filename)

@router.get("", response_model=list[KnowledgeOut])
def list_documents(db: Session = Depends(get_db)):
    return service.list_documents(db)

@router.put("/{knowledge_id}", response_model=KnowledgeOut)
def update_document(knowledge_id: int, data: KnowledgeUpdate, db: Session = Depends(get_db)):
    return service.update_document(db, knowledge_id, data.title, data.content, data.source)
@router.delete("/{knowledge_id}") #删除操作没有实体返回，故不使用 response_model
def delete_document(knowledge_id: int, db: Session = Depends(get_db)):
    return service.delete_document(db, knowledge_id)
