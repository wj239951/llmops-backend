# -*- coding: utf-8 -*-
"""pytest 公共 fixture。

关键点：在 import app 之前 patch 掉 chromadb.PersistentClient ——
否则 rag_service 模块在 import 时就会打开真实 Chroma（甚至触发 l2→cosine 重建）。
"""
import chromadb
from unittest.mock import MagicMock, patch

# 让 rag_service 的 _open_vectorstore() 不碰真实 Chroma
_fake_collection = MagicMock()
_fake_collection.metadata = {"hnsw:space": "cosine"}
_fake_client = MagicMock()
_fake_client.get_collection.return_value = _fake_collection
patch("chromadb.PersistentClient", return_value=_fake_client).start()

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

# 确保模型注册到 Base.metadata（和 database.init_db 里 import 的一致）
import app.models.prompt  # noqa: E402,F401
import app.models.knowledge  # noqa: E402,F401
import app.models.chat_log  # noqa: E402,F401
import app.models.conversation  # noqa: E402,F401

from app.core.database import Base, get_db  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture()
def db_engine():
    """每个测试一个独立的 SQLite in-memory 数据库（不碰 MySQL）。"""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture()
def db_session(db_engine):
    Session = sessionmaker(bind=db_engine, autoflush=False, autocommit=False)
    db = Session()
    yield db
    db.close()


@pytest.fixture()
def client(db_engine):
    """FastAPI TestClient，把 get_db 依赖换成 SQLite。"""
    TestingSession = sessionmaker(bind=db_engine, autoflush=False, autocommit=False)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def auth_headers():
    return {"Authorization": f"Bearer {settings.DEMO_PASSWORD}"}
