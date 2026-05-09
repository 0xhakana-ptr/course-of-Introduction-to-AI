"""Messaging package exports.

Keep this module light to avoid importing `message_sender` during package
initialization, which would otherwise create circular imports for schema-only
consumers.
"""

__all__: list[str] = []
