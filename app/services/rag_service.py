# 知识库业务逻辑，包括保存知识、检索知识、拼接上下文。##检索增强索引
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models.knowledge import KnowledgeDocument
from sqlalchemy import or_
import jieba
import os
# 在文件顶部读取
stop_words_file = os.path.join(str(os.path.dirname(__file__)), "Disable_word_list.txt")
with open(stop_words_file, encoding="utf-8") as f:
    stop_words = set(f.read().split())
class RAGService:
    def add_document(self, db: Session, title: str, content: str, source: str | None = None):
        doc = KnowledgeDocument(title=title, content=content, source=source)
        db.add(doc); db.commit(); db.refresh(doc)
        return doc

    def list_documents(self, db: Session):
        return db.query(KnowledgeDocument).order_by(KnowledgeDocument.id.desc()).all()

    def search(self, db: Session, query: str, limit: int = 3):
        keywords = [w for w in jieba.lcut_for_search(query) if w.strip() and w.isalnum() and w not in stop_words]#结巴分词，不按照空格分割，同时舍弃停用词
        if not keywords:
            """
            如果没有关键词，则返回空列表
            避免后续检索时检索全局内容
            """
            return []
        conditions = [KnowledgeDocument.content.like(f"%{kw}%") for kw in keywords]#生成条件列表，每条文档，如果关键词在文档内容中，则返回该文档（对conditions定义，条件列表）
        candidates = db.query(KnowledgeDocument).filter(or_(*conditions)).all()
        # 对每条候选，数它命中了几个关键词
        scored = []
        for doc in candidates:
            score = sum(1 for kw in keywords if kw in doc.content)
            scored.append((score, doc))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [doc for _, doc in scored[:limit]]

    def build_context(self, docs):
        return "\n\n".join(
            f"[知识片段{i}] 标题：{doc.title}\n内容：{doc.content[:1200]}"
            for i, doc in enumerate(docs, start=1)
        )

    def update_document(self, db: Session, knowledge_id: int, title: str | None = None, content: str | None = None,
                        source: str | None = None):
        """根据 ID 更新知识库文档"""
        doc = db.query(KnowledgeDocument).filter(KnowledgeDocument.id == knowledge_id).first()
        if not doc:
            raise HTTPException(status_code=404, detail=f"知识库文档不存在，ID: {knowledge_id}")

        if title is not None:
            doc.title = title
        if content is not None:
            doc.content = content
        if source is not None:
            doc.source = source

        db.commit()
        db.refresh(doc)
        return doc

    def delete_document(self, db, knowledge_id):
        db.query(KnowledgeDocument).filter(KnowledgeDocument.id == knowledge_id).delete()
        db.commit()
        return {"message": "知识库文档删除成功"}
