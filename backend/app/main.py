import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .api import agent_router, chat_router, health_router, llm_router, message_router, run_router
from .api.error_handlers import register_exception_handlers
from .core.config import settings
from .core.logging_config import configure_logging
from .services.run_interface import recover_interrupted_runs
from .storage.conversation_store import conversation_store


configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    pruned_conversations = conversation_store.prune_storage(force=True)
    if pruned_conversations > 0:
        logger.info(
            "Conversation storage cleanup completed: removed_count=%s",
            pruned_conversations,
        )
    app.state.startup_recovery = recover_interrupted_runs()
    recovery = app.state.startup_recovery
    if recovery.recovered_count > 0:
        logger.warning(
            "Startup recovery completed: recovered_count=%s scanned_count=%s",
            recovery.recovered_count,
            recovery.scanned_count,
        )
    else:
        logger.info("Startup recovery completed: scanned_count=%s", recovery.scanned_count)
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="AI Chat Backend", version=settings.app_version, lifespan=lifespan)
    register_exception_handlers(app)
    app.include_router(health_router)
    app.include_router(llm_router)
    app.include_router(agent_router)
    app.include_router(chat_router)
    app.include_router(run_router)
    app.include_router(message_router)
    return app


app = create_app()
