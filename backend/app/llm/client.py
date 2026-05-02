from backend.app.core.config import settings


async def call_llm(prompt: str, context: str | None = None) -> str:
    if not settings.llm_api_key:
        return (
            "当前还没有配置真实大模型密钥。\n\n"
            f"收到的 prompt: {prompt}\n"
            f"context: {context or '(none)'}"
        )
        
    # 这里先留占位，后续再接具体供应商
    return (
        "这里将来替换成真实 LLM 返回。\n\n"
        f"model={settings.llm_model}\n"
        f"prompt={prompt}\n"
        f"context={context or '(none)'}"
    )
