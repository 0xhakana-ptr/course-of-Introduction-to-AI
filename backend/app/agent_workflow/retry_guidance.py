import importlib as _importlib
import sys as _sys

_impl = _importlib.import_module(".repair.retry_guidance", __package__)

_sys.modules[__name__] = _impl
