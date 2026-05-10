import importlib as _importlib
import sys as _sys

_impl = _importlib.import_module(".contracts.workflow_results", __package__)

_sys.modules[__name__] = _impl
