"""
conftest.py — Shared fixtures for Kaori data-pipeline unit tests.

Path & import bootstrap
-----------------------
The service at services/data-pipeline/ uses intra-package relative imports
(``from ..shared.db import get_pool``, ``from .routers import upload`` …).
These only work when the directory is imported **as a package**, i.e. when
Python knows the parent package name.

We solve this by registering the directory under a synthetic package name
``data_pipeline`` (underscore, because Python identifiers cannot contain
hyphens) via ``importlib`` before any test module runs.  After bootstrap:

  * ``import data_pipeline.main`` works and resolves relative imports
  * ``import routers.upload`` *also* works because ``services/data-pipeline``
    is still on sys.path (allows direct-import style used in unit tests)
  * Both ``data_pipeline.shared.db`` and ``shared.db`` refer to the same
    underlying module object

The conftest.py at the tests/ level runs before any test collection, so this
bootstrap is guaranteed to execute first.
"""
import importlib
import importlib.util
import sys
import types
from pathlib import Path

import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Resolve directory paths
# ---------------------------------------------------------------------------
_SERVICE_ROOT = Path(__file__).resolve().parent.parent          # services/data-pipeline/
_REPO_ROOT    = _SERVICE_ROOT.parent.parent                      # D:/Kaori System/

# Add both to sys.path so bare imports (``import routers.upload``) also work
for _p in (_SERVICE_ROOT, _REPO_ROOT):
    _s = str(_p)
    if _s not in sys.path:
        sys.path.insert(0, _s)

# ---------------------------------------------------------------------------
# Register the service directory as the ``data_pipeline`` package so that
# relative imports inside main.py / routers / bronze / silver resolve.
# ---------------------------------------------------------------------------
_PKG_NAME = "data_pipeline"

if _PKG_NAME not in sys.modules:
    # Create the top-level package entry
    _pkg = types.ModuleType(_PKG_NAME)
    _pkg.__path__ = [str(_SERVICE_ROOT)]
    _pkg.__package__ = _PKG_NAME
    _pkg.__spec__ = importlib.util.spec_from_file_location(
        _PKG_NAME,
        str(_SERVICE_ROOT / "__init__.py"),
        submodule_search_locations=[str(_SERVICE_ROOT)],
    )
    sys.modules[_PKG_NAME] = _pkg

    # Do NOT pre-register sub-packages as empty ModuleType stubs — they would
    # shadow the real packages (routers/, bronze/, silver/, etc.) that have
    # their own __init__.py. Python's import machinery can find them via the
    # top-level package's __path__ when "import data_pipeline.routers.clean"
    # is executed for the first time.


# ---------------------------------------------------------------------------
# Core DataFrame fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_df() -> pd.DataFrame:
    """
    Standard test DataFrame with four columns representing common real-world
    data types found in uploaded files:
      - name   : object (string) — clean
      - amount : float           — numeric money column
      - date   : object          — dates stored as strings (not yet parsed)
      - phone  : object          — Vietnamese phone numbers
    """
    return pd.DataFrame({
        "name":   ["Alice", "Bob", "Charlie", "Diana"],
        "amount": [1000.0, 2500.5, 300.0, 99.99],
        "date":   ["01/03/2024", "15/06/2023", "30/12/2022", "07/01/2024"],
        "phone":  ["0901234567", "0912345678", "0923456789", "0934567890"],
    })


@pytest.fixture
def sample_df_with_nulls() -> pd.DataFrame:
    """DataFrame with nulls and whitespace to exercise cleaning rules."""
    return pd.DataFrame({
        "name":   ["  Alice  ", None, "Bob", "nan", ""],
        "amount": [100.0, None, 200.0, None, 300.0],
        "date":   ["01/03/2024", None, None, "15/06/2023", None],
        "phone":  ["+84901234567", None, "84912345678", "0923456789", "invalid"],
    })


@pytest.fixture
def minimal_language_dict() -> dict:
    """
    Tiny language dictionary for isolating column_mapper tests.
    Matches the shape of config/language_dictionary.json entries.
    """
    return {
        "customer_name": {
            "data_type": "text",
            "vi": ["tên khách hàng", "họ tên", "tên"],
            "en": ["customer name", "name", "full name"],
            "ja": ["顧客名", "氏名"],
        },
        "amount": {
            "data_type": "currency",
            "vi": ["số tiền", "thành tiền", "tiền"],
            "en": ["amount", "total", "price"],
        },
        "transaction_date": {
            "data_type": "date",
            "vi": ["ngày giao dịch", "ngày", "ngày tháng"],
            "en": ["date", "transaction date", "trans date"],
        },
        "phone": {
            "data_type": "phone",
            "vi": ["điện thoại", "số điện thoại", "sdt"],
            "en": ["phone", "phone number", "mobile"],
        },
    }
