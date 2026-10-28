"""Compatibility re-export → services.run_interface.

The run implementation lives in ``run_interface.py``; this module keeps the
historical ``services.run`` import path working.
"""

from .run_interface import *  # noqa: F401, F403
