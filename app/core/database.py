# 创建 MySQL 连接、 Session 会话、初始化数据库表。
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from app.core.config import settings

class Base(DeclarativeBase):
    pass

engine = create_engine(settings.SQLALCHEMY_DATABASE_URL,
                       pool_pre_ping=True,
                       pool_recycle=3600,
                       echo=False
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    import app.models.prompt  # noqa: F401
    import app.models.knowledge  # noqa: F401
    import app.models.chat_log  # noqa: F401
    import app.models.conversation  # noqa: F401
    Base.metadata.create_all(bind=engine)
