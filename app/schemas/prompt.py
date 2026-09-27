# Prompt 新增、修改、返回数据结构。
from datetime import datetime
from pydantic import BaseModel, Field

class PromptCreate(BaseModel):
    name: str
    description: str | None = None
    system_prompt: str
    model_provider: str = "ollama"
    model_name: str | None = None
    temperature: float = Field(default=0.7, ge=0, le=2)
    top_p: float = Field(default=0.9, ge=0, le=1)
    enabled: bool = True

class PromptUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    system_prompt: str | None = None
    model_provider: str | None = None
    model_name: str | None = None
    temperature: float | None = None
    top_p: float | None = None
    enabled: bool | None = None

class PromptOut(BaseModel):
    id: int
    name: str
    description: str | None
    system_prompt: str
    model_provider: str
    model_name: str | None
    temperature: float
    top_p: float
    enabled: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
