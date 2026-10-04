"""
从 MySQL 读出所有 KnowledgeDocument
提取 content 字段
用 Chroma.from_texts() 存入
调用 vectorstore.persist() 保存到本地目录
"""
import sys
import os
from pathlib import Path
os.chdir(Path(__file__).parent.parent)
sys.path.insert(0, str(Path(__file__).parent.parent))
from app.core.database import SessionLocal
from app.models.knowledge import KnowledgeDocument
from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.vectorstores import Chroma


def migrate():
    # 1. 从 MySQL 读取所有文档
    db = SessionLocal()
    try:
        docs = db.query(KnowledgeDocument).all()
        print(f"从数据库读取到 {len(docs)} 条文档")
    finally:
        db.close()

    if not docs:
        print("没有文档需要迁移")
        return

    # 2. 提取文本内容（标题 + 正文，让标题也参与检索权重）
    texts = [f"{doc.title}：{doc.content}" for doc in docs]

    # 3. 初始化嵌入模型
    print("正在初始化 bge-m3 嵌入模型...")
    embeddings = OllamaEmbeddings(model="bge-m3")

    # 4. 创建 Chroma 向量库并持久化
    persist_dir = str(Path(__file__).parent.parent / "chroma_db")
    print(f"正在将 {len(texts)} 条文档转向量并存入 Chroma...")
    vectorstore = Chroma.from_texts(
        texts=texts,
        embedding=embeddings,
        persist_directory=persist_dir
    )

    # 5. 创建 Chroma 向量库并持久化
    vectorstore.persist()
    print(f"迁移完成！向量库保存在：{persist_dir}")


if __name__ == "__main__":
    migrate()
