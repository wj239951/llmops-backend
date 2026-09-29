# 知识库业务逻辑，包括保存知识、检索知识、拼接上下文。##检索增强索引
from sqlalchemy.orm import Session
from app.models.knowledge import KnowledgeDocument

class RAGService:
    def add_document(self, db: Session, title: str, content: str, source: str | None = None):
        doc = KnowledgeDocument(title=title, content=content, source=source)
        db.add(doc); db.commit(); db.refresh(doc)
        return doc

    def list_documents(self, db: Session):
        return db.query(KnowledgeDocument).order_by(KnowledgeDocument.id.desc()).all()

    def search(self, db: Session, query: str, limit: int = 3):
        keywords = [x.strip() for x in query.replace("，", " ").replace(",", " ").split() if x.strip()]
        q = db.query(KnowledgeDocument)
        for kw in keywords[:5]:
            q = q.filter(KnowledgeDocument.content.like(f"%{kw}%"))
        return q.order_by(KnowledgeDocument.id.desc()).limit(limit).all()

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
            raise ValueError(f"知识库文档不存在，ID: {knowledge_id}")

        if title is not None:
            doc.title = title
        if content is not None:
            doc.content = content
        if source is not None:
            doc.source = source

        db.commit()
        db.refresh(doc)
        return doc
