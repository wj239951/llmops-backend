# -*- coding: utf-8 -*-
"""RAG search 回归测试（mock 向量库 + SQLite 文档，不碰真实 Chroma/Ollama）。"""
from unittest.mock import MagicMock

import pytest

from app.models.knowledge import KnowledgeDocument
from app.services import rag_service
from app.services.rag_service import RAGService, RetrievedChunk


def _make_hit(doc_id, page_content, distance):
    """伪造一条 (Document, distance)，distance 是 Chroma 的 1-cosine。"""
    doc = MagicMock()
    doc.metadata = {"id": doc_id, "title": "t", "chunk": 0}
    doc.page_content = page_content
    return doc, distance


def test_empty_query_returns_empty(db_session):
    assert RAGService().search(db_session, "   ") == []


def test_search_converts_distance_to_cosine(db_session, monkeypatch):
    d = KnowledgeDocument(title="标题", content="正文")
    db_session.add(d)
    db_session.commit()
    db_session.refresh(d)

    # distance=0.4 → cosine 应为 0.6
    monkeypatch.setattr(
        rag_service.vectorstore,
        "similarity_search_with_score",
        MagicMock(return_value=[_make_hit(d.id, "正文", 0.4)]),
    )

    hits = RAGService().search(db_session, "查询")
    assert len(hits) == 1
    assert hits[0].title == "标题"
    assert hits[0].content == "正文"
    assert hits[0].score == pytest.approx(0.6)


def test_orphan_hit_is_skipped(db_session, monkeypatch):
    # metadata 指向一个 MySQL 里不存在的 id → 应被跳过，返回空（不静默假命中）
    monkeypatch.setattr(
        rag_service.vectorstore,
        "similarity_search_with_score",
        MagicMock(return_value=[_make_hit(99999, "孤儿向量", 0.1)]),
    )
    assert RAGService().search(db_session, "查询") == []


def test_build_context_contains_title_and_content():
    chunks = [RetrievedChunk(title="A", content="正文内容", source=None, score=0.9)]
    ctx = RAGService().build_context(chunks)
    assert "标题：A" in ctx
    assert "正文内容" in ctx
