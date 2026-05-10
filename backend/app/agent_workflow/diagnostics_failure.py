import importlib as _importlib
import sys as _sys

_impl = _importlib.import_module(".diagnostics.failure", __package__)

_sys.modules[__name__] = _impl
