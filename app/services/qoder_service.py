# 调用 Qoder Cloud Agents API（会话式：建 session -> 发消息 -> 轮询 events 拼回答）。
# 注意：Qoder 没有 chat completions 那种一次调用接口，只能驱动云端 agent 跑一轮，
# 所以单轮耗时会比 ollama / deepseek 久（几十秒级）。
import time
import requests
from app.core.config import settings

class QoderService:

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {settings.QODER_API_KEY}",
            "Content-Type": "application/json",
        }

    def _get(self, path: str, params: dict | None = None) -> dict:
        resp = requests.get(
            f"{settings.QODER_BASE_URL}{path}",
            params=params,
            headers=self._headers(),
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, body: dict) -> dict:
        resp = requests.post(
            f"{settings.QODER_BASE_URL}{path}",
            json=body,
            headers=self._headers(),
            timeout=30,
        )
        if not resp.ok:
            # 把服务端返回的 body 带进异常，方便直接看出 400 的具体原因
            raise ValueError(f"Qoder 接口 {path} 返回 {resp.status_code}：{resp.text}")
        return resp.json()

    def _pick_model_id(self) -> str:
        # 模型目录按账号解析，文档示例的 ultimate 你账号上不一定有，先拉真实列表再选。
        models = self._get("/api/v1/cloud/models").get("data") or []
        ids = [m.get("id") for m in models if m.get("is_enabled")]
        if settings.QODER_AGENT_MODEL in ids:
            return settings.QODER_AGENT_MODEL
        if not ids:
            raise ValueError("Qoder 账号下没有可用模型，请到控制台检查模型列表。")
        return ids[0]

    def _pick_agent_id(self) -> str:
        # 优先用 .env 里指定的 agent；没指定就取账号下第一个；还没有就按快速入门的格式建一个。
        if settings.QODER_AGENT_ID:
            return settings.QODER_AGENT_ID
        data = self._get("/api/v1/cloud/agents", {"limit": 1}).get("data") or []
        if data:
            return data[0]["id"]
        agent = self._post("/api/v1/cloud/agents", {
            "name": "llmops-chat-agent",
            "model": self._pick_model_id(),
            "system": "你是工业 LLMOps 平台中的智能助手，请准确、简洁地回答用户问题。",
            # 不配 tools：平台只把 Qoder 当问答提供商用，agent 不需要在云沙箱里跑工具，
            # 少一层配置就少一层 400 风险，回答也更快更省 credits
        })
        agent_id = agent.get("id")
        if not agent_id:
            raise ValueError(f"Qoder 创建 agent 失败：{agent}")
        return agent_id

    def _pick_environment_id(self) -> str:
        # 运行环境（云端沙箱）同理：先取第一个，没有就建默认环境。
        if settings.QODER_ENVIRONMENT_ID:
            return settings.QODER_ENVIRONMENT_ID
        data = self._get("/api/v1/cloud/environments", {"limit": 1}).get("data") or []
        if data:
            return data[0]["id"]
        env = self._post("/api/v1/cloud/environments", {"name": "default"})
        env_id = env.get("id")
        if not env_id:
            raise ValueError(f"Qoder 创建 environment 失败：{env}")
        return env_id

    def _create_session(self, query: str) -> str:
        # 建 session，agent 和 environment 是必填项；CN 文档里 agent 直接传 ID 字符串。
        session = self._post("/api/v1/cloud/sessions", {
            "agent": self._pick_agent_id(),
            "environment_id": self._pick_environment_id(),
            "title": query[:30],
        })
        session_id = session.get("id") or session.get("data", {}).get("id")
        if not session_id:
            raise ValueError(f"Qoder 创建 session 失败：{session}")
        return session_id

    def _send_message(self, session_id: str, text: str):
        # 把拼好的整段文本作为 user.message event 发进 session。
        self._post(f"/api/v1/cloud/sessions/{session_id}/events", {
            "events": [{"type": "user.message", "content": [{"type": "text", "text": text}]}],
        })

    def _collect_answer(self, session_id: str) -> str:
        # 轮询 events，收集 agent.message 里的文本，直到本轮跑完或超时。
        answer_parts = []
        seen_ids = set()
        deadline = time.time() + settings.QODER_TIMEOUT
        status = ""
        while time.time() < deadline:
            time.sleep(3)
            events = self._get(f"/api/v1/cloud/sessions/{session_id}/events", {"limit": 100}).get("data") or []
            for ev in events:
                ev_id = ev.get("id")
                if ev_id in seen_ids:
                    continue
                seen_ids.add(ev_id)
                if ev.get("type") == "agent.message":
                    for block in ev.get("content") or []:
                        if block.get("text"):
                            answer_parts.append(block["text"])
            status = self._get(f"/api/v1/cloud/sessions/{session_id}").get("status") or ""
            # 收到回答且 session 不再运行，视为本轮结束
            if answer_parts and status not in ("running", "processing", "pending"):
                break
            if status in ("completed", "archived", "cancelled", "failed", "error"):
                break
        answer = "\n".join(answer_parts).strip()
        if not answer:
            raise ValueError(f"Qoder session 超时或未返回回答（最后状态：{status or '未知'}）。")
        return answer

    def chat(self, query: str, system_prompt: str, model_name: str | None = None,
             temperature: float = 0.7, top_p: float = 0.9,
             history: list | None = None) -> dict:
        if not settings.QODER_API_KEY:
            raise ValueError("QODER_API_KEY 未配置，请用 setx 把 Qoder 个人访问令牌写入系统环境变量。")
        model = model_name or settings.QODER_MODEL

        # 会话式接口不收 messages 数组，系统提示词、历史、当前问题只能拼成一整段文本
        parts = [system_prompt]
        for msg in history or []:
            role = "用户" if msg["role"] == "user" else "助手"
            parts.append(f"{role}：{msg['content']}")
        parts.append(f"用户：{query}")
        full_text = "\n".join(parts)

        session_id = self._create_session(query)
        self._send_message(session_id, full_text)
        answer = self._collect_answer(session_id)
        return {
            "answer": answer,
            "reasoning": "",
            "model_provider": "qoder",
            "model_name": model,
            # Cloud Agents 接口不返回 token 数
            "total_tokens": 0,
        }
