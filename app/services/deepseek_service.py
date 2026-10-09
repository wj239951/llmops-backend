# 调用 DeepSeek 官方 API（兼容 OpenAI SDK）。
from openai import OpenAI
from app.core.config import settings

class DeepSeekService:
    def chat(self, query: str, system_prompt: str, model_name: str | None = None,
             temperature: float = 0.7, top_p: float = 0.9,
             history: list[dict] | None = None) -> dict:
        if not settings.DEEPSEEK_API_KEY or settings.DEEPSEEK_API_KEY == "your_deepseek_api_key":
            raise ValueError("DEEPSEEK_API_KEY 未配置，请在 backend/.env 中填写真实 DeepSeek Key。")
        model = model_name or settings.DEEPSEEK_MODEL
        client = OpenAI(api_key=settings.DEEPSEEK_API_KEY, base_url=settings.DEEPSEEK_BASE_URL)

        # 会话记忆：system -> 历史(用户/助手) -> 当前问题
        messages = [{"role": "system", "content": system_prompt}]
        for msg in history or []:
            messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": query})

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            top_p=top_p,
        )
        message = response.choices[0].message
        answer = message.content or ""
        # deepseek-reasoner 会把思考过程放在 reasoning_content 字段里，deepseek-chat 没有
        reasoning = getattr(message, "reasoning_content", "") or ""
        return {
            "answer": answer,
            "reasoning": reasoning,
            "model_provider": "deepseek",
            "model_name": model,
            "total_tokens": response.usage.total_tokens if response.usage else 0,
        }
