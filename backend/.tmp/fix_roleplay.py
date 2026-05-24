"""Add emit_vision_quip() to RoleplayAgent."""
import pathlib

path = pathlib.Path(r"D:\codeAIAGENT\cyber-waifu-vue\backend\app\agent_workflow\roleplay.py")
content = path.read_text("utf-8")

# The method to insert BEFORE emit_idle_quip_if_due
new_method = '''
    def emit_vision_quip(self, analysis):
        """Layer 2 vision-aware quip: uses character personality + vision observation.

        Connects the vision pipeline to the roleplay layer so the character
        reacts naturally to what it sees on the user's screen.

        Args:
            analysis: dict from vision.analyzer.analyze_activity() with keys:
                activity_label, element_summary, mood_hint, has_content

        Returns:
            bool: True if quip was generated and sent.
        """
        activity = analysis.get("activity_label", "unknown")
        elements = analysis.get("element_summary", "")
        mood_hint = analysis.get("mood_hint", "neutral")

        if not llm_is_configured():
            logger.warning("Vision quip skipped: LLM not configured")
            message_sender.send_error(
                code="vision.llm_not_configured",
                message="LLM not configured for vision quip",
                node_name="vision_monitor",
                event_type="system.error",
                event_source="vision",
                event_stage="system",
            )
            return False

        # Build vision-aware prompt
        vision_prompt = (
            f"\u7075\u80fd\u611f\u77e5\u62a5\u544a\uff1a\u7528\u6237\u5c4f\u5e55\u4e0a\u68c0\u6d4b\u5230 "
            f"{elements}\uff0c\u6d3b\u52a8\u7c7b\u578b\u5224\u5b9a\u4e3a\u300c{activity}\u300d\u3002"
            f"\n\u8bf7\u6839\u636e\u4ee5\u4e0a\u5c4f\u5e55\u89c2\u5bdf\uff0c\u4ee5\u89d2\u8272\u8eab\u4efd\u751f\u6210\u4e00\u53e5\u81ea\u7136\u7684 quip"
            f"\uff08\u226430\u5b57\uff09\u3002\u4e0d\u8981\u8f93\u51fa chat_line\uff0c\u53ea\u8f93\u51fa quip + expression\u3002"
            f"\n\u8bb0\u4f4f\uff1a\u4f60\u662f\u684c\u9762\u5c0f\u7cbe\u7075\u300c\u672a\u547d\u540d\u300d\uff0c\u4f60\u5728\u5077\u770b\u7528\u6237\u7684\u5c4f\u5e55\u3002"
        )

        mood = get_session_mood()
        state_context = (
            f"\u5c4f\u5e55\u89c2\u5bdf: {elements}\n"
            f"\u6d3b\u52a8: {activity}\n"
            f"\u60c5\u7eea\u6697\u793a: {mood_hint}"
        )
        system_prompt = ROLEPLAY_SYSTEM_PROMPT.format(
            state_context=state_context,
            mood_modifier=mood.modifier_text,
        )

        try:
            result = call_llm_sync(
                prompt=vision_prompt,
                context=None,
                system_prompt=system_prompt,
                temperature=0.85,
                max_tokens=120,
            )
        except Exception as exc:
            logger.exception("Vision LLM call failed")
            message_sender.send_error(
                code="vision.llm_call_failed",
                message=f"LLM error: {str(exc)[:200]}",
                node_name="vision_monitor",
                event_type="system.error",
                event_source="vision",
                event_stage="system",
            )
            return False

        if not result.ok or not result.output:
            logger.warning("Vision LLM failed: ok=%s error=%s", result.ok, getattr(result, "error", ""))
            message_sender.send_error(
                code="vision.llm_failed",
                message=f"LLM returned error: {getattr(result, 'error', 'unknown')[:200]}",
                node_name="vision_monitor",
                event_type="system.error",
                event_source="vision",
                event_stage="system",
            )
            return False

        parsed = _parse_llm_json(result.output)
        if not parsed:
            logger.warning("Vision LLM parse failed: %s", repr(result.output[:200]))
            return False

        quip = str(parsed.get("quip", "")).strip()
        expression = str(parsed.get("expression", "neutral")).strip()

        if not quip:
            return False

        # Send through standard roleplay frontend channels
        message_sender.send_quip(
            content=quip,
            node_name="vision_monitor",
            priority="medium",
            duration=4500,
            event_type="character.quip",
            event_source="character",
            event_stage="roleplay",
            metadata={
                "event_source": "vision_monitor",
                "phase": activity,
            },
        )
        message_sender.send_expression(
            expression=expression,
            node_name="vision_monitor",
            intensity=0.75,
            duration=4000,
            transition="smooth",
            mode="set",
            event_type="character.expression",
            event_source="character",
            event_stage="roleplay",
        )

        mood.idle_streak = 0
        mood.record_neutral()
        logger.info("Vision quip sent via Layer2: activity=%s quip=%s expr=%s", activity, quip, expression)
        return True

'''

# Insert before emit_idle_quip_if_due
marker = "    def emit_idle_quip_if_due(self):"
if marker in content:
    content = content.replace(marker, new_method + marker)
    path.write_text(content, "utf-8")
    print("emit_vision_quip() added to RoleplayAgent")
else:
    print("MARKER NOT FOUND")
    # Find the last method before emit_idle
    for i, line in enumerate(content.split("\n")):
        if "emit_idle" in line:
            print(f"Line {i+1}: {line}")
