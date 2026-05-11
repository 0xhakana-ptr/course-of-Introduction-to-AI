import logging

from backend.app.core.logging_config import resolve_log_level


def test_resolve_log_level_supports_standard_level_names():
    assert resolve_log_level("DEBUG") == logging.DEBUG
    assert resolve_log_level("warning") == logging.WARNING


def test_resolve_log_level_falls_back_to_info_for_unknown_values():
    assert resolve_log_level("not-a-level") == logging.INFO
