# 聊天请求、返回数据结构。
from pydantic import BaseModel

class ChatRequest(BaseModel):
    query: str
    prompt_id: int | None = None
    system_prompt: str | None = None
    model_provider: str | None = None
    model_name: str | None = None
    temperature: float = 0.7
    top_p: float = 0.9
    use_rag: bool = False
    ##
    conversation_id: str | None = None# 聊天会话 ID
    memory_enabled: bool = False# 是否启用内存
    ##
class ChatResponse(BaseModel):
    answer: str
    reasoning: str | None = None
    thought: str
    model_provider: str
    model_name: str
    total_tokens: int
    latency_ms: int
    ##
    conversation_id: str | None = None# 聊天会话 ID
    sources: list[dict] = []
    ##