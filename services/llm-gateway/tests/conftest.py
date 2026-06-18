"""
conftest.py — Path/import bootstrap for llm-gateway tests.

The service directory is named ``llm-gateway`` (hyphenated) which is not
a valid Python identifier. The Docker image copies the source into
``/app/llm_gateway/`` and uvicorn loads it as the ``llm_gateway`` (under-
score) package. We mirror that setup for tests so

    from llm_gateway.router import router
    from llm_gateway.pii   import redact

resolve the same way they do at runtime.

Two sys.path entries are registered:

  * ``services/llm-gateway/``  — so the flat-style ``from error_codes``
    imports inside ``errors.py`` resolve (matches the
    notification-service / data-pipeline convention; in Docker the same
    files end up at the package root).
  * repo root                  — so cross-service helpers stay importable
    without test-only shims.
"""
import importlib.util
import sys
import types
from pathlib import Path

_SERVICE_ROOT = Path(__file__).resolve().parent.parent  # services/llm-gateway/
_REPO_ROOT = _SERVICE_ROOT.parent.parent                 # repo root

for _p in (_SERVICE_ROOT, _REPO_ROOT):
    _s = str(_p)
    if _s not in sys.path:
        sys.path.insert(0, _s)

_PKG_NAME = "llm_gateway"
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
