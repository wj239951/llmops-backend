# 读取 .env 配置，统一管理数据库地址、 Ollama 地址、 DeepSeek Key 、 Qoder 令牌 。

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
    QODER_API_KEY: str = ""# 个人访问令牌（PAT），从系统环境变量读
    QODER_BASE_URL: str = "https://api.qoder.com.cn"# CN 站网关；国际站是 api.qoder.com
    QODER_MODEL: str = "qoder-cloud-agent"
    QODER_AGENT_MODEL: str = "ultimate"# 建 agent 时用的模型档位
    QODER_AGENT_ID: str = ""# 留空则自动取账号下第一个 agent
    QODER_ENVIRONMENT_ID: str = ""# 留空则自动取账号下第一个 environment
    QODER_TIMEOUT: int = 180# 轮询回答的超时秒数
    MEMORY_MAX_TURNS: int = 10

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