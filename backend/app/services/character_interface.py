from ..messaging.message_sender import message_sender
from .character_action.events import (
    CHAT_DONE_EVENT,
    CHAT_FAILED_EVENT,
    CHAT_STARTED_EVENT,
    TASK_CANCELLED_EVENT,
    TASK_DONE_EVENT,
    TASK_FAILED_EVENT,
    TASK_QUEUED_EVENT,
    TASK_REPAIRING_EVENT,
    TASK_STARTED_EVENT,
    CharacterEvent,
)


def dispatch_character_event(event: CharacterEvent) -> bool:
    results: list[bool] = []
    if event.quip:
        results.append(
            message_sender.send_quip(
                content=event.quip,
                node_name=event.node_name,
                priority=event.priority,
                duration=event.duration,
            )
        )
    if event.expression:
        results.append(
            message_sender.send_expression(
                expression=event.expression,
                node_name=event.node_name,
                duration=event.duration,
                mode="set",
            )
        )
    if event.motion:
        results.append(
            message_sender.send_motion(
                motion=event.motion,
                node_name=event.node_name,
                duration=event.duration,
            )
        )
    if event.status:
        results.append(
            message_sender.send_status(
                status=event.status,
                progress=event.progress,
                node_name=event.node_name,
            )
        )
    return all(results) if results else True


def send_chat_started() -> bool:
    return dispatch_character_event(CHAT_STARTED_EVENT)


def send_chat_done() -> bool:
    return dispatch_character_event(CHAT_DONE_EVENT)


def send_chat_failed() -> bool:
    return dispatch_character_event(CHAT_FAILED_EVENT)


def send_task_queued() -> bool:
    return dispatch_character_event(TASK_QUEUED_EVENT)


def send_task_started() -> bool:
    return dispatch_character_event(TASK_STARTED_EVENT)


def send_task_repairing() -> bool:
    return dispatch_character_event(TASK_REPAIRING_EVENT)


def send_task_done() -> bool:
    return dispatch_character_event(TASK_DONE_EVENT)


def send_task_failed() -> bool:
    return dispatch_character_event(TASK_FAILED_EVENT)


def send_task_cancelled() -> bool:
    return dispatch_character_event(TASK_CANCELLED_EVENT)
