import logging
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .api import agent_router, chat_router, health_router, llm_router, message_router, run_router, vision_router, workspace_router
from .api.error_handlers import register_exception_handlers
from .core.config import settings
from .core.logging_config import configure_logging
from .services.run import recover_interrupted_runs
from .services.run import RunServiceImpl
from .agent_workflow.actions.ports import bind_run_port
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

    # Start idle quip background loop
    idle_task = asyncio.create_task(_idle_quip_loop())

    # Start vision monitor background loop
    vision_task = asyncio.create_task(_vision_monitor_loop())

    yield

    idle_task.cancel()
    vision_task.cancel()
    for task in (idle_task, vision_task):
        try:
            await task
        except asyncio.CancelledError:
            pass


def create_app() -> FastAPI:
    app = FastAPI(title="AI Chat Backend", version=settings.app_version, lifespan=lifespan)
    register_exception_handlers(app)

    # Bind agent ports to service implementations
    bind_run_port(RunServiceImpl())

    app.include_router(health_router)
    app.include_router(llm_router)
    app.include_router(agent_router)
    app.include_router(chat_router)
    app.include_router(run_router)
    app.include_router(workspace_router)
    app.include_router(message_router)
    app.include_router(vision_router)
    return app


async def _idle_quip_loop():
    """Periodically check and emit idle quips when the agent is inactive."""
    from .agent_workflow.roleplay import roleplay_agent
    while True:
        await asyncio.sleep(6)
        try:
            roleplay_agent.emit_idle_quip_if_due()
        except Exception:
            pass


async def _vision_monitor_loop():
    """Background vision monitor: screenshot -> ONNX inference -> quip."""
    try:
        from .vision.monitor import vision_monitor
        await vision_monitor.run_loop()
    except ImportError as exc:
        import logging
        logging.getLogger(__name__).error("Vision monitor disabled (import failed): %s", exc)
    except Exception:
        import logging
        logging.getLogger(__name__).exception("Vision monitor crashed")


app = create_app()
