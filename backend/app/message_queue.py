# Compatibility re-export: real implementation lives in messaging/queue.py
from .messaging.queue import MessageQueue, message_queue  # noqa: F401

__all__ = ["MessageQueue", "message_queue"]