# 知识库业务逻辑，包括保存知识、检索知识、拼接上下文。##检索增强索引
from dataclasses import dataclass
from fastapi import HTTPException
#from langchain_community import embeddings
from sqlalchemy.orm import Session
from app.models.knowledge import KnowledgeDocument
#from sqlalchemy import or_
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import OllamaEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

#import jieba
import os

# 在文件顶部读取
stop_words_file = os.path.join(str(os.path.dirname(__file__)), "Disable_word_list.txt")
embeddings = OllamaEmbeddings(model="bge-m3")
vectorstore = Chroma(persist_directory="./chroma_db", embedding_function=embeddings, collection_name="knowledge_bge_m3")
# 长文档切分成小片段再向量化：既能避免超出 bge-m3 上下文长度，又能让检索命中更精准的段落。
# separators 加了中文标点，优先在句子边界切分。
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=50,
    separators=["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""],
)
with open(stop_words_file, encoding="utf-8") as f:
    stop_words = set(f.read().split())


@dataclass
class RetrievedChunk:
    """检索命中的知识片段。content 是切分后的片段原文，不是整篇文档。"""
    title: str
    content: str
    source: str | None


class RAGService:
    def add_document(self, db: Session, title: str, content: str, source: str | None = None):
        doc = KnowledgeDocument(title=title, content=content, source=source)
        db.add(doc)
        db.commit()
        db.refresh(doc)
        self._sync_to_chroma(doc)
        return doc

    def list_documents(self, db: Session):
        return db.query(KnowledgeDocument).order_by(KnowledgeDocument.id.desc()).all()
    #注释掉关键词索引
    #
    # def search(self, db: Session, query: str, limit: int = 3):
    #     keywords = [w for w in jieba.lcut_for_search(query) if w.strip() and w.isalnum() and w not in stop_words]#结巴分词，不按照空格分割，同时舍弃停用词
    #     if not keywords:
    #         """
    #         如果没有关键词，则返回空列表
    #         避免后续检索时检索全局内容
    #         """
    #         return []
    #     conditions = [KnowledgeDocument.content.like(f"%{kw}%") for kw in keywords]#生成条件列表，每条文档，如果关键词在文档内容中，则返回该文档（对conditions定义，条件列表）
    #     candidates = db.query(KnowledgeDocument).filter(or_(*conditions)).all()
    #     # 对每条候选，数它命中了几个关键词
    #     scored = []
    #     for doc in candidates:
    #         score = sum(1 for kw in keywords if kw in doc.content)
    #         scored.append((score, doc))
    #     scored.sort(key=lambda x: x[0], reverse=True)
    #     return [doc for _, doc in scored[:limit]]
    def search(self, db: Session, query: str, limit: int = 3):
        if not query.strip():
            return []
        # 检索的是文档切分后的片段(chunk)，命中更精准；返回片段原文而非整篇文档
        results = vectorstore.similarity_search(query, k=limit)
        chunks = []
        for r in results:
            doc = self._convert_to_knowledge_doc(db, r)
            if doc is None:
                continue
            chunks.append(RetrievedChunk(title=doc.title, content=r.page_content, source=doc.source))
        return chunks

    def build_context(self, docs):
        return "\n\n".join(
            f"[知识片段{i}] 标题：{doc.title}\n内容：{doc.content}"
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
        # 一篇文档对应多个 chunk 向量，按 metadata 里的文档 id 删除它的全部片段
        vectorstore._collection.delete(where={"id": knowledge_id})
        self._sync_to_chroma(doc)
        return doc

    def delete_document(self, db, knowledge_id):
        db.query(KnowledgeDocument).filter(KnowledgeDocument.id == knowledge_id).delete()
        db.commit()
        vectorstore._collection.delete(where={"id": knowledge_id})
        return {"message": "知识库文档删除成功"}

    def _convert_to_knowledge_doc(self, db: Session, r):
        """
        从 r.metadata["id"] 拿到 MySQL 主键
        用这个 id 去 db 里查 KnowledgeDocument
        查到就返回，查不到返回 None
        """
        doc_id = r.metadata.get("id")
        if doc_id is None:
            return None
        return db.query(KnowledgeDocument).filter(KnowledgeDocument.id == doc_id).first()

    def _sync_to_chroma(self, doc):
        """把一条知识库文档切分成片段后写入 Chroma，每个片段一个向量；片段 id 用 '文档id_序号'"""
        text = f"{doc.title}：{doc.content}"
        chunks = text_splitter.split_text(text)
        ids = [f"{doc.id}_{i}" for i in range(len(chunks))]
        # metadata 里的 id 存 MySQL 主键，检索时用它反查文档；chunk 记录片段序号
        metadatas = [{"id": doc.id, "title": doc.title, "chunk": i} for i in range(len(chunks))]
        # 必须走 LangChain 包装层的 add_texts，它才会用配置的 bge-m3(1024维) 生成向量；
        # 若直接调 _collection.add(documents=...)，chromadb 会用自带的默认模型(384维)，导致读写维度不一致。
        vectorstore.add_texts(
            texts=chunks,
            metadatas=metadatas,
            ids=ids,
        )
        