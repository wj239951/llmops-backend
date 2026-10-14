# 知识库业务逻辑，包括保存知识、检索知识、拼接上下文。##检索增强索引
from dataclasses import dataclass
from fastapi import HTTPException
#from langchain_community import embeddings
from sqlalchemy.orm import Session
from app.models.knowledge import KnowledgeDocument
#from sqlalchemy import or_
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import OllamaEmbeddings
from langchain_core.embeddings import Embeddings
from openai import OpenAI
from app.core.config import settings
from langchain_text_splitters import RecursiveCharacterTextSplitter
import chromadb
#import jieba
import logging
import os

# 在文件顶部读取
stop_words_file = os.path.join(str(os.path.dirname(__file__)), "Disable_word_list.txt")

logger = logging.getLogger(__name__)


class SiliconFlowEmbeddings(Embeddings):
    """硅基流动 bge-m3 向量化。直接用 openai 客户端对接其 OpenAI 兼容端点,
    避开 langchain OpenAIEmbeddings 对 tiktoken/transformers 的依赖(容器里都没装)。"""

    def __init__(self, model: str, base_url: str, api_key: str):
        self._client = OpenAI(base_url=base_url, api_key=api_key)
        self._model = model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        resp = self._client.embeddings.create(model=self._model, input=list(texts))
        return [d.embedding for d in resp.data]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


def _build_embeddings():
    # 按部署环境选向量化通道:本地有 Ollama 走它;云上没 Ollama 走硅基流动(同 bge-m3 权重,老向量兼容)
    if settings.EMBEDDING_PROVIDER == "siliconflow":
        return SiliconFlowEmbeddings(
            model=settings.SILICONFLOW_EMBEDDING_MODEL,
            base_url=settings.SILICONFLOW_EMBEDDING_BASE_URL,
            api_key=settings.SILICONFLOW_API_KEY,
        )
    return OllamaEmbeddings(
        model=settings.OLLAMA_EMBEDDING_MODEL,
        base_url=settings.OLLAMA_EMBEDDING_BASE_URL,
    )


# 必须在 _open_vectorstore() 之前实例化，后者引用它
embeddings = _build_embeddings()

# chroma_db 绝对路径：不依赖进程 CWD，从任意目录启动都能定位到同一个库
_CHROMA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "chroma_db",
)

_COLLECTION = "knowledge_bge_m3"
_SPACE = {"hnsw:space": "cosine"}


def _open_vectorstore():
    """打开/重建向量库。space 只在建 collection 时生效，旧 space 改不了，必须重建。"""
    client = chromadb.PersistentClient(path=_CHROMA_DIR)
    try:
        col = client.get_collection(_COLLECTION)
    except Exception:
        col = None
    if col is not None and (col.metadata or {}).get("hnsw:space") != "cosine":
        print(f"[rag_service] collection '{_COLLECTION}' 是旧 l2 空间，删除重建为 cosine。")
        client.delete_collection(_COLLECTION)   # 只有确认 space 不对才删
        col = None
    if col is None:
        client.create_collection(_COLLECTION, metadata=_SPACE)
        print(f"[rag_service] 已创建 cosine collection '{_COLLECTION}'；"
              f"向量需从 MySQL 重新灌：migrate_to_chroma.py --apply。")
    return Chroma(
        client=client,
        collection_name=_COLLECTION,
        embedding_function=embeddings,
    )


vectorstore = _open_vectorstore()
# 长文档切分成小片段再向量化：既能避免超出 bge-m3 上下文长度，又能让检索命中更精准的段落。
# separators 加了中文标点，优先在句子边界切分。
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,#分块长度
    chunk_overlap=50,#分块重叠
    separators=["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""],
)
with open(stop_words_file, encoding="utf-8") as f:
    stop_words = set(f.read().split())


@dataclass
class RetrievedChunk:
    title: str
    content: str
    source: str | None
    score: float          # cosine 相似度（= 1 - distance），越大越相关


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
    # search() 换成带分数的检索
    def search(self, db: Session, query: str, limit: int = 3):
        if not query.strip():
            return []
        results = vectorstore.similarity_search_with_score(query, k=limit)
        chunks = []
        for r, score in results:
            doc = self._convert_to_knowledge_doc(db, r)
            if doc is None:
                # 命中但反查 MySQL 失败 = 孤儿向量（文档已删但向量没删干净）。
                # 不静默跳过，记 warning，否则和"真·未命中"在日志里长得一样、没法排查。
                logger.warning(
                    "RAG 命中片段在 MySQL 中找不到对应文档，已跳过（疑似孤儿向量，"
                    "建议清理 Chroma 里对应 id 的向量）：metadata=%s",
                    dict(r.metadata or {}),
                )
                continue
            chunks.append(RetrievedChunk(
                title=doc.title, content=r.page_content, source=doc.source,
                score=float(1.0 - score),  # distance → cosine：越大越相关，方便直接跟阈值比
            ))
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
        # 只向量化正文，不拼标题前缀：标题已通过 metadata 反查 + build_context 单独展示。
        # 之前 f"{doc.title}：{doc.content}" 会让每条向量共享同一段标题开头，
        # 结构性抬高 cosine 基线（"查询全挤在 0.36–0.44" 的第三个原因）。
        text = doc.content
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
        