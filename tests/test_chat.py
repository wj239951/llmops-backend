# -*- coding: utf-8 -*-
"""聊天接口回归测试（鉴权 + RAG 三态），LLM/RAG 全 mock，不碰 Ollama/Chroma/MySQL。"""
from app.services.llm_service import LLMService
from app.services.rag_service import RAGService, RetrievedChunk

FAKE_RESULT = {
    "answer": "测试回答",
    "reasoning": "",
    "model_provider": "ollama",
    "model_name": "test-model",
    "total_tokens": 10,
}


def test_chat_requires_auth(client):
    r = client.post("/api/chat", json={"query": "你好"})
    assert r.status_code == 401


def test_chat_rejects_wrong_auth(client):
    r = client.post(
        "/api/chat",
        json={"query": "你好"},
        headers={"Authorization": "Bearer wrong"},
    )
    assert r.status_code == 401


def test_chat_no_hit(client, auth_headers, monkeypatch):
    monkeypatch.setattr(LLMService, "chat", lambda self, **kw: FAKE_RESULT)
    monkeypatch.setattr(RAGService, "search", lambda self, db, query: [])

    r = client.post(
        "/api/chat",
        json={"query": "今天中午吃什么", "use_rag": True},
        headers=auth_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["answer"] == "测试回答"
    assert body["rag_status"] == "no_hit"
    assert body["sources"] == []


def test_chat_hit(client, auth_headers, monkeypatch):
    monkeypatch.setattr(LLMService, "chat", lambda self, **kw: FAKE_RESULT)
    monkeypatch.setattr(
        RAGService,
        "search",
        lambda self, db, query: [RetrievedChunk(title="标题", content="内容", source=None, score=0.7)],
    )

    r = client.post(
        "/api/chat",
        json={"query": "润滑脂型号是什么", "use_rag": True},
        headers=auth_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["rag_status"] == "hit"
    assert len(body["sources"]) == 1
    assert body["sources"][0]["title"] == "标题"
    assert body["sources"][0]["score"] == 0.7
