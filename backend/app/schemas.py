from typing import Literal
from pydantic import BaseModel, Field


INTENT_TYPE = Literal["chat", "coding", "unknown"]
RUN_STATUS = Literal["queued", "running", "done", "failed"]


class ChatRequest(BaseModel):
    prompt: str = Field(..., min_length=1, description="用户输入")
    context: str | None = Field(default=None, description="对话上下文")
    

class ChatResponse(BaseModel):
    ok: bool = True
    intent: INTENT_TYPE
    output: str


class RunCreateRequest(BaseModel):
    prompt: str = Field(..., min_length=1, description="任务输入")
    context: str | None = Field(default=None, description="任务上下文")


class RunResponse(BaseModel):
    run_id: str
    status: RUN_STATUS
    output: str
    created_at: str
    updated_at: str
