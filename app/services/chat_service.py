# 聊天核心业务流程，负责读取 Prompt、处理 RAG、调用模型、写入日志。
import time
import uuid
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.chat_log import ChatLog
from app.models.conversation import Conversation
from app.schemas.chat import ChatRequest
from app.services.llm_service import LLMService
from app.services.prompt_service import PromptService
from app.services.rag_service import RAGService
from app.core.config import settings

class ChatService:

    def __init__(self):
        self.llm = LLMService()
        self.prompt_service = PromptService()
        self.rag = RAGService()
    def new_conversation_id(self) -> str:
        return str(uuid.uuid4())
    ##会话记忆
    def _load_history(self, db: Session, conversation_id: str | None, limit: int) -> list[dict]:
        # 从 ChatLog 中读取同一会话最近若干轮成功对话，作为上下文记忆。
        if not conversation_id or limit <= 0:
            return []
        logs = (
            db.query(ChatLog)
            .filter(
                ChatLog.conversation_id == conversation_id,
                ChatLog.status == "success",
            )
            .order_by(ChatLog.created_at.desc(), ChatLog.id.desc())
            .limit(limit)
            .all()
        )
        logs.reverse()
        history: list[dict] = []
        for log in logs:
            history.append({"role": "user", "content": log.user_input})
            if log.assistant_output:
                history.append({"role": "assistant", "content": log.assistant_output})
        return history
    ##
    def _ensure_conversation(self, db: Session, conversation_id: str | None, query: str):
        # 确保 conversations 表中有该会话记录；首次对话时自动用问题前30字做标题。
        if not conversation_id:
            return
        conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
        if not conv:
            title = query[:30] if len(query) > 30 else query
            conv = Conversation(id=conversation_id, title=title)
            db.add(conv)
        elif conv.title == "新会话":
            conv.title = query[:30] if len(query) > 30 else query
        conv.updated_at = datetime.utcnow()
        db.commit()
    ##
    def chat(self, db: Session, req: ChatRequest):
        start = time.time()
        prompt_name = None
        system_prompt = req.system_prompt or "你是工业 LLMOps 平台中的智能助手，请准确、简洁地回答。"
        provider = req.model_provider or "ollama"
        model_name = req.model_name
        temperature = req.temperature
        top_p = req.top_p

        workflow_reasoning = [
            f"用户问题：{req.query}",
            f"模型提供商：{provider}",
            f"模型名称：{model_name or '默认模型'}",
            "步骤1：读取用户输入。",
            "步骤2：加载系统提示词。",
        ]
        if req.prompt_id:
            prompt = self.prompt_service.get(db, req.prompt_id)
            if prompt:
                prompt_name = prompt.name
                system_prompt = prompt.system_prompt
                provider = req.model_provider or prompt.model_provider or provider
                model_name = req.model_name or prompt.model_name
                temperature = prompt.temperature
                top_p = prompt.top_p
                workflow_reasoning.append(f"步骤3：使用 Prompt 模板：{prompt_name}。")
            else:
                workflow_reasoning.append("步骤3：未找到指定 Prompt，使用默认系统提示词。")
        else:
            workflow_reasoning.append("步骤3：未选择 Prompt，使用默认系统提示词。")

        ## 加载会话记忆（历史对话上下文）
        history: list[dict] = []
        if req.memory_enabled and req.conversation_id:
            history = self._load_history(db, req.conversation_id, settings.MEMORY_MAX_TURNS)
            workflow_reasoning.append(
                f"步骤4：加载会话记忆，conversation_id={req.conversation_id}，"
                f"共 {len(history) // 2} 轮历史对话。"
            )
        else:
            workflow_reasoning.append("步骤4：未启用会话记忆或无 conversation_id，本轮为独立对话。")
        ##
        final_query = req.query
        rag_docs = []
        if req.use_rag:
            rag_docs = self.rag.search(db, req.query)
            context = self.rag.build_context(rag_docs)
            if context:
                final_query = (
                    "请基于以下知识库内容回答问题。\n"
                    "如果知识库内容不足，请说明不足，再结合通用知识补充。\n\n"
                    f"{context}\n\n用户问题：{req.query}"
                )
                workflow_reasoning.append(f"步骤5：启用 RAG，检索到 {len(rag_docs)} 条知识片段。")
            else:
                workflow_reasoning.append("步骤5：启用 RAG，但未检索到有效知识片段。")
        else:
            workflow_reasoning.append("步骤5：未启用 RAG，直接调用模型。")

        try:
            workflow_reasoning.append("步骤6：调用大模型生成回答。")
            result = self.llm.chat(
                query=final_query,
                system_prompt=system_prompt,
                provider=provider,
                model_name=model_name,
                temperature=temperature,
                top_p=top_p,
                history=history,
            )
            # 记录日志（携带 conversation_id，用于后续会话记忆检索）
            latency_ms = int((time.time() - start) * 1000)
            db.add(
                ChatLog(
                    ##
                    conversation_id=req.conversation_id,#用于给模型精准投喂历史会话，避免出现多次历史记录一次投给模型
                    ##
                    user_input=req.query,
                    assistant_output=result["answer"],
                    model_provider=result["model_provider"],
                    model_name=result["model_name"],
                    prompt_name=prompt_name,
                    total_tokens=result["total_tokens"],
                    latency_ms=latency_ms,
                    status="success",
                )
            )
            db.commit()
            self._ensure_conversation(db, req.conversation_id, req.query)
            workflow_reasoning.append("步骤7：模型回答生成完成。")
            workflow_reasoning.append("步骤8：将调用日志写入数据库。")
            workflow_reasoning.append(f"步骤9：本次调用耗时 {latency_ms} ms。")
            thought = (
                "已调用本地 Ollama 模型 deepseek-r1:7b，并完成 Prompt/RAG/会话记忆/日志流程。"
                if result["model_provider"] == "ollama"
                else "已调用 DeepSeek 云端 API 模式，并完成 Prompt/RAG/会话记忆/日志流程。"
            )
            reasoning = result.get("reasoning") or "\n".join(workflow_reasoning)
            return {
                "answer": result["answer"],
                "reasoning": reasoning,
                "thought": thought,
                "model_provider": result["model_provider"],
                "model_name": result["model_name"],
                "total_tokens": result["total_tokens"],
                "latency_ms": latency_ms,
                "conversation_id": req.conversation_id,
                "sources": [
                    {"title": d.title, "snippet": d.content[:200], "source": d.source}
                    for d in rag_docs
                ],
            }
        except Exception as e:
            latency_ms = int((time.time() - start) * 1000)
            db.add(
                ChatLog(
                    ##
                    conversation_id=req.conversation_id,# 会话ID
                    ##
                    user_input=req.query,
                    assistant_output="",
                    model_provider=provider or "unknown",
                    model_name=model_name or "unknown",
                    prompt_name=prompt_name,
                    total_tokens=0,
                    latency_ms=latency_ms,
                    status="failed",
                    error_message=str(e),
                )
            )
            db.commit()
            raise
