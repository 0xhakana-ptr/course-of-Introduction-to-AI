"""ONE-SHOT: write all vision module fixes. No PowerShell string manipulation."""
import pathlib, textwrap

BASE = pathlib.Path(r"D:\codeAIAGENT\cyber-waifu-vue\backend")

# ===== 1. roleplay.py: add emit_vision_quip before emit_idle_quip_if_due =====
rp = BASE / "app/agent_workflow/roleplay.py"
rp_text = rp.read_text("utf-8")

vision_method = '''
    def emit_vision_quip(self, analysis):
        """Layer 2 vision-aware quip: uses character personality + screen observation."""
        activity = analysis.get("activity_label", "unknown")
        elements = analysis.get("element_summary", "")
        mood_hint = analysis.get("mood_hint", "neutral")

        if not llm_is_configured():
            logger.warning("Vision quip skipped: LLM not configured")
            return False

        vision_prompt = (
            f"[Screen] {elements}, activity: {activity}. "
            f"You are desktop sprite Unnamed, you peeked at the user screen. "
            f"React with ONE natural, cheeky quip (<=30 chars). "
            f'Output ONLY valid JSON: {{"quip": "<=30 char quip", "expression": "name"}}'
        )

        mood = get_session_mood()
        state_context = f"Screen: {elements}\\nActivity: {activity}\\nMood hint: {mood_hint}"
        system_prompt = ROLEPLAY_SYSTEM_PROMPT.format(
            state_context=state_context,
            mood_modifier=mood.modifier_text,
        )

        try:
            result = call_llm_sync(
                prompt=vision_prompt, context=None,
                system_prompt=system_prompt, temperature=0.85, max_tokens=2000,
            )
        except Exception as exc:
            logger.exception("Vision LLM call failed")
            return False

        if not result.ok or not result.output:
            logger.warning("Vision LLM failed: ok=%s", result.ok)
            return False

        parsed = _parse_llm_json(result.output)
        if not parsed:
            return False

        quip = str(parsed.get("quip", "")).strip()
        expression = str(parsed.get("expression", "neutral")).strip()
        if not quip:
            return False

        message_sender.send_quip(
            content=quip, node_name="vision_monitor", priority="medium", duration=4500,
            event_type="character.quip", event_source="character", event_stage="roleplay",
            metadata={"event_source": "vision_monitor", "phase": activity},
        )
        message_sender.send_expression(
            expression=expression, node_name="vision_monitor",
            intensity=0.75, duration=4000, transition="smooth", mode="set",
            event_type="character.expression", event_source="character", event_stage="roleplay",
        )
        mood.idle_streak = 0
        mood.record_neutral()
        logger.info("Vision quip sent via Layer2: activity=%s quip=%s expr=%s", activity, quip, expression)
        return True

'''

marker = "    def emit_idle_quip_if_due(self):"
if marker in rp_text:
    rp_text = rp_text.replace(marker, vision_method + marker)
    rp.write_text(rp_text, "utf-8")
    print("1. roleplay.py: emit_vision_quip() added")
else:
    print("1. roleplay.py: MARKER NOT FOUND - ABORT")
    raise SystemExit(1)

# ===== 2. api/__init__.py: add vision_router =====
api_init = BASE / "app/api/__init__.py"
api_text = api_init.read_text("utf-8")
if "vision_router" not in api_text:
    api_text = api_text.replace(
        'from .workspace_routes import router as workspace_router',
        'from .vision_routes import router as vision_router\nfrom .workspace_routes import router as workspace_router'
    )
    api_text = api_text.replace(
        '"workspace_router",',
        '"vision_router",\n    "workspace_router",'
    )
    api_init.write_text(api_text, "utf-8")
    print("2. api/__init__.py: vision_router added")
else:
    print("2. api/__init__.py: already done")

# ===== 3. main.py: register vision_router + _vision_monitor_loop =====
main_py = BASE / "app/main.py"
main_text = main_py.read_text("utf-8")
if "vision_router" not in main_text:
    main_text = main_text.replace(
        "from .api import agent_router, chat_router, health_router, llm_router, message_router, run_router, workspace_router",
        "from .api import agent_router, chat_router, health_router, llm_router, message_router, run_router, vision_router, workspace_router"
    )
    main_text = main_text.replace(
        "app.include_router(message_router)\n    return app",
        "app.include_router(message_router)\n    app.include_router(vision_router)\n    return app"
    )
    # Add _vision_monitor_loop
    if "_vision_monitor_loop" not in main_text:
        old_idle = "async def _idle_quip_loop():"
        new_vision_loop = '''
async def _vision_monitor_loop():
    """Background vision monitor: screenshot -> ONNX -> Layer2 roleplay -> quip."""
    try:
        from .vision.monitor import vision_monitor
        await vision_monitor.run_loop()
    except ImportError as exc:
        import logging
        logging.getLogger(__name__).error("Vision monitor disabled (import failed): %s", exc)
    except Exception:
        import logging
        logging.getLogger(__name__).exception("Vision monitor crashed")

async def _idle_quip_loop():'''
        main_text = main_text.replace(old_idle, new_vision_loop.strip())
    # Add vision_task to lifespan
    if "vision_task" not in main_text:
        main_text = main_text.replace(
            "idle_task = asyncio.create_task(_idle_quip_loop())",
            "idle_task = asyncio.create_task(_idle_quip_loop())\n\n    # Start vision monitor background loop\n    vision_task = asyncio.create_task(_vision_monitor_loop())"
        )
        main_text = main_text.replace(
            "idle_task.cancel()",
            "idle_task.cancel()\n    vision_task.cancel()"
        )
        main_text = main_text.replace(
            "for task in (idle_task,):",
            "for task in (idle_task, vision_task):"
        )
    main_py.write_text(main_text, "utf-8")
    print("3. main.py: vision_router + _vision_monitor_loop added")
else:
    print("3. main.py: already done")

# ===== 4. Verify everything imports =====
import sys
sys.path.insert(0, str(BASE))
from app.agent_workflow.roleplay import roleplay_agent
assert hasattr(roleplay_agent, "emit_vision_quip"), "MISSING emit_vision_quip"
print("4. VERIFY: roleplay_agent.emit_vision_quip OK")

from app.main import app
routes = [r.path for r in app.routes if "vision" in str(r.path)]
print(f"5. VERIFY: vision routes = {routes}")

from app.vision.monitor import vision_monitor, _IMPORT_ERRORS
print(f"6. VERIFY: vision_monitor OK, import_errors={_IMPORT_ERRORS or 'none'}")

print("\\nALL DONE - restart uvicorn now")
