from typing import Literal


AGENT_ROUTE_BY_INTENT: dict[str, str] = {
    "coding": "coding_node",
    "chat": "chat_node",
    "unknown": "unknown_node",
}

WORKFLOW_NODE_FAILED_STATUS = "workflow_node_failed"

RUN_ACTION_CREATE: Literal["create"] = "create"
RUN_ACTION_INSPECT: Literal["inspect"] = "inspect"
RUN_ACTION_RETRY: Literal["retry"] = "retry"
RUN_ACTION_RERUN: Literal["rerun"] = "rerun"
RUN_ACTION_CANCEL: Literal["cancel"] = "cancel"

RUN_CONTROL_ACTIONS = {
    RUN_ACTION_RETRY,
    RUN_ACTION_RERUN,
    RUN_ACTION_CANCEL,
}
