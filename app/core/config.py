# 读取 .env 配置，统一管理数据库地址、 Ollama 地址、 DeepSeek Key 、向量化通道 。

from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    APP_NAME: str = "Industrial LLMOps Ollama Local"
    APP_ENV: str = "local"
    API_PREFIX: str = "/api"
    MYSQL_HOST: str = "127.0.0.1"
    MYSQL_PORT: int = 3306
    MYSQL_DATABASE: str = "llmops_db"
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = ""
    DEFAULT_MODEL_PROVIDER: str = "ollama"
    OLLAMA_BASE_URL: str = "http://127.0.0.1:11434"
    OLLAMA_MODEL: str = "deepseek-r1:7b"
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL: str = "deepseek-v4-pro"
    MEMORY_MAX_TURNS: int = 10

    # embedding provider 开关:"ollama" | "siliconflow"
    EMBEDDING_PROVIDER: str = "ollama"
    # ollama embedding(本地)
    OLLAMA_EMBEDDING_BASE_URL: str = "http://localhost:11434"
    OLLAMA_EMBEDDING_MODEL: str = "bge-m3"
    # siliconflow embedding(云上)
    SILICONFLOW_EMBEDDING_BASE_URL: str = "https://api.siliconflow.cn/v1"
    SILICONFLOW_EMBEDDING_MODEL: str = "BAAI/bge-m3"
    SILICONFLOW_API_KEY: str = ""
    @property
    def SQLALCHEMY_DATABASE_URL(self) -> str:
        return (
            f"mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}"
            "?charset=utf8mb4"
        )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8"
    )


settings = Settings()