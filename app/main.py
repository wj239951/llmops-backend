# FastAPI 主入口，注册路由、配置 CORS、启动时初始化数据库。
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import init_db
from app.api.chat import router as chat_router
from app.api.prompt import router as prompt_router
from app.api.knowledge import router as knowledge_router
from app.api.logs import router as logs_router
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {
        "name": settings.APP_NAME,
        "mode": "local",
        "database": "MySQL 8.x",
        "local_model": settings.OLLAMA_MODEL,
        "ollama_base_url": settings.OLLAMA_BASE_URL,
        "chatgpt_mode": "OpenAI API Key",
        "docker": False,
        "virtual_machine": False,
    }

app.include_router(chat_router, prefix=settings.API_PREFIX)
app.include_router(prompt_router, prefix=settings.API_PREFIX)
app.include_router(knowledge_router, prefix=settings.API_PREFIX)
app.include_router(logs_router, prefix=settings.API_PREFIX)
