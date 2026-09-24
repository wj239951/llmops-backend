# 调用本地 Ollama 接口，访问 deepseek-r1:7b 模型。
import re
import requests
from app.core.config import settings

class OllamaService:
    def _split_reasoning_and_answer(self, raw_text: str, data: dict) -> tuple[str, str]:
        reasoning = ""

        possible_reasoning_fields = [
            data.get("thinking"),
            data.get("reasoning"),
            data.get("thought"),
            data.get("message", {}).get("thinking") if isinstance(data.get("message"), dict) else None,
            data.get("message", {}).get("reasoning") if isinstance(data.get("message"), dict) else None,
            data.get("message", {}).get("thought") if isinstance(data.get("message"), dict) else None,
        ]
        for item in possible_reasoning_fields:
            if item:
                reasoning = str(item).strip()
                break
        answer = (
            raw_text
            or data.get("response", "")
            or (
                data.get("message", {}).get("content", "")
                if isinstance(data.get("message"), dict)
                else ""
            )
            or ""
        )
        # 格式1：<think>...</think>
        think_match = re.search(
            r"<think>(.*?)</think>",
            answer,
            flags=re.DOTALL | re.IGNORECASE,
        )
        if think_match:
            reasoning = think_match.group(1).strip()
            answer = re.sub(
                r"<think>.*?</think>",
                "",
                answer,
                flags=re.DOTALL | re.IGNORECASE,
            ).strip()
            return reasoning, answer
        # 格式2：缺少开头 <think>，但有 </think>
        if "</think>" in answer:
            parts = answer.split("</think>", 1)
            reasoning = parts[0].replace("<think>", "").strip()
            answer = parts[1].strip()
            return reasoning, answer
        # 格式3：Ollama 终端常见显示：Thinking... ...done thinking.
        thinking_match = re.search(
            r"Thinking\.\.\.(.*?)\.\.\.done thinking\.",
            answer,
            flags=re.DOTALL | re.IGNORECASE,
        )
        if thinking_match:
            reasoning = thinking_match.group(1).strip()
            answer = re.sub(
                r"Thinking\.\.\..*?\.\.\.done thinking\.",
                "",
                answer,
                flags=re.DOTALL | re.IGNORECASE,
            ).strip()
            return reasoning, answer
        return reasoning.strip(), answer.strip()

    def chat(
        self,
        query: str,
        system_prompt: str,
        model_name: str | None = None,
        temperature: float = 0.7,
        top_p: float = 0.9,
        ##
        history: list[dict] | None = None,
        ##
    ) -> dict:
        model = model_name or settings.OLLAMA_MODEL
        ##会话记忆模块
        history_block = ""
        if history:
            lines = []
            for msg in history:#遍历对话历史
                role = "用户" if msg.get("role") == "user" else "助手"#确定模板
                content = (msg.get("content") or "").strip()#删除空格
                if content:#删除删除掉空格后没有内容的行
                    lines.append(f"{role}：{content}")
            if lines:
                history_block = (
                    "\n以下是历史对话记录，请结合上下文回答最新问题：\n"
                    + "\n".join(lines)
                    + "\n"
                )#生成提示词
        ##

        prompt = f"""系统提示词：
{system_prompt}
##
{history_block}
##
用户问题：
{query}
"""

        session = requests.Session()
        session.trust_env = False

        response = session.post(
            f"{settings.OLLAMA_BASE_URL}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "top_p": top_p,
                },
            },
            timeout=300,
        )
        if response.status_code != 200:
            raise RuntimeError(
                f"Ollama调用失败：{response.status_code}，内容：{response.text}"
            )
        data = response.json()
        raw_answer = data.get("response", "")
        reasoning, final_answer = self._split_reasoning_and_answer(
            raw_text=raw_answer,
            data=data,
        )

        return {
            "answer": final_answer,
            "reasoning": reasoning,
            "model_provider": "ollama",
            "model_name": model,
            "total_tokens": data.get("prompt_eval_count", 0) + data.get("eval_count", 0),
        }
