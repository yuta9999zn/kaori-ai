"""
conftest.py — Path/import bootstrap for ai-orchestrator tests.

The service directory is named `ai-orchestrator` (hyphenated) which is not
a valid Python identifier. Tests reference the package as `ai_orchestrator`
(underscore). We register the service root under that synthetic name so
that ``import ai_orchestrator.agents.framework_router`` resolves during
test collection.

Python's import machinery will then find real sub-packages (agents,
analytics, consumers, engine, routers, shared) via the parent package's
__path__ — no need to pre-stub them.
"""
import importlib.util
import sys
import types
from pathlib import Path

_SERVICE_ROOT = Path(__file__).resolve().parent.parent  # services/ai-orchestrator/
_REPO_ROOT = _SERVICE_ROOT.parent.parent                 # repo root

for _p in (_SERVICE_ROOT, _REPO_ROOT):
    _s = str(_p)
    if _s not in sys.path:
        sys.path.insert(0, _s)

_PKG_NAME = "ai_orchestrator"
if _PKG_NAME not in sys.modules:
    _pkg = types.ModuleType(_PKG_NAME)
    _pkg.__path__ = [str(_SERVICE_ROOT)]
    _pkg.__package__ = _PKG_NAME
    _pkg.__spec__ = importlib.util.spec_from_file_location(
        _PKG_NAME,
        str(_SERVICE_ROOT / "__init__.py"),
        submodule_search_locations=[str(_SERVICE_ROOT)],
    )
    sys.modules[_PKG_NAME] = _pkg
