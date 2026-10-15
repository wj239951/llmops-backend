# -*- coding: utf-8 -*-
"""Prompt CRUD 回归测试（service 层，SQLite in-memory，不碰 MySQL）。"""
from app.schemas.prompt import PromptCreate, PromptUpdate
from app.services.prompt_service import PromptService


def test_create(db_session):
    svc = PromptService()
    p = svc.create(db_session, PromptCreate(name="测试模板", system_prompt="你是助手"))
    assert p.id is not None
    assert p.name == "测试模板"
    assert p.model_provider == "ollama"


def test_list_and_get(db_session):
    svc = PromptService()
    svc.create(db_session, PromptCreate(name="a", system_prompt="x"))
    svc.create(db_session, PromptCreate(name="b", system_prompt="y"))
    rows = svc.list(db_session)
    assert len(rows) == 2
    assert svc.get(db_session, rows[0].id) is not None


def test_update(db_session):
    svc = PromptService()
    p = svc.create(db_session, PromptCreate(name="旧名字", system_prompt="x"))
    updated = svc.update(db_session, p.id, PromptUpdate(name="新名字"))
    assert updated is not None
    assert updated.name == "新名字"


def test_delete(db_session):
    svc = PromptService()
    p = svc.create(db_session, PromptCreate(name="要删的", system_prompt="x"))
    assert svc.delete(db_session, p.id) is True
    assert svc.get(db_session, p.id) is None
    # 再删一次应返回 False（幂等、不抛异常）
    assert svc.delete(db_session, p.id) is False
