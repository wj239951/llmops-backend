# 统一封装模型调用，根据 provider 选择 Ollama 或 OpenAI。
from app.services.ollama_service import OllamaService
from app.services.openai_service import OpenAIService
from app.core.config import settings

class LLMService:
    def __init__(self):
        self.ollama = OllamaService()
        self.openai = OpenAIService()

    def chat(self, query: str, system_prompt: str, provider: str | None = None,
             model_name: str | None = None, temperature: float = 0.7, top_p: float = 0.9,
             ##
             history: list[dict] | None = None) -> dict:
             ##
        provider = provider or settings.DEFAULT_MODEL_PROVIDER
        if provider == "ollama":
            ##
            return self.ollama.chat(query, system_prompt, model_name, temperature, top_p, history)
            ##
        if provider == "openai":
            return self.openai.chat(query, system_prompt, model_name, temperature, top_p)#openai打不开，暂时不写
        raise ValueError(f"不支持的模型提供商：{provider}")
