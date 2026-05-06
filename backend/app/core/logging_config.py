import logging

from .config import settings


LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


def resolve_log_level(level_name: str | None = None) -> int:
    raw_name = (level_name or settings.log_level).strip().upper()
    return getattr(logging, raw_name, logging.INFO)


def configure_logging(*, force: bool = False) -> None:
    level = resolve_log_level()
    root_logger = logging.getLogger()

    if root_logger.handlers and not force:
        root_logger.setLevel(level)
        return

    logging.basicConfig(
        level=level,
        format=LOG_FORMAT,
        force=force,
    )
