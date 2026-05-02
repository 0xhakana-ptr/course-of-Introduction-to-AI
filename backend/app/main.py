from fastapi import FastAPI, HTTPException

from backend.app.core.config import settings
from backend.app.schemas import ChatRequest, ChatResponse, RunCreateRequest, RunResponse
from backend.app.services.chat_service import generate_chat_response
from backend.app.services.run_service import create_run, get_run


app = FastAPI(title="AI Chat Backend", version=settings.app_version)


@app.get("/health")
async def health():
    return {
        "ok": True,
        "service": "backend",
        "version": settings.app_version
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    prompt = req.prompt.strip()
    context = (req.context or "").strip() or None

    intent, output = await generate_chat_response(prompt, context)
    return ChatResponse(intent=intent, output=output)


@app.post("/runs", response_model=RunResponse)
async def create_run_route(req: RunCreateRequest):
    prompt = req.prompt.strip()
    context = (req.context or "").strip() or None
    return create_run(prompt, context)


@app.get("/runs/{run_id}", response_model=RunResponse)
async def get_run_route(run_id: str):
    run = get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return run
