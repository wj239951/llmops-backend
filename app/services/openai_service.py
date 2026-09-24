# 调用 ChatGPT / OpenAI API Key 模型。
from openai import OpenAI
from app.core.config import settings

class OpenAIService:
    def chat(self, query: str, system_prompt: str, model_name: str | None = None,
             temperature: float = 0.7, top_p: float = 0.9) -> dict:
        if not settings.OPENAI_API_KEY or settings.OPENAI_API_KEY == "your_openai_api_key":
            raise ValueError("OPENAI_API_KEY 未配置，请在 backend/.env 中填写真实 ChatGPT/OpenAI Key。")
        model = model_name or settings.OPENAI_MODEL
        client = OpenAI(api_key=settings.OPENAI_API_KEY, base_url=settings.OPENAI_BASE_URL)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query},
            ],
            temperature=temperature,
            top_p=top_p,
        )
        return {
            "answer": response.choices[0].message.content or "",
            "model_provider": "openai",
            "model_name": model,
            "total_tokens": response.usage.total_tokens if response.usage else 0,
        }
