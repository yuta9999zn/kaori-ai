"""
conftest.py — path bootstrap for notification-service tests.

The service uses a flat layout (no package — ``main.py``, ``config.py``
etc. sit at the service root and are imported by ``main:app`` directly
via uvicorn). Tests live one level down in ``tests/``, so we need to
add the service root to ``sys.path`` for ``from outbox_poller import
OutboxPoller`` to resolve during pytest collection.
"""
import sys
from pathlib import Path

_SERVICE_ROOT = Path(__file__).resolve().parent.parent  # services/notification-service/
if str(_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(_SERVICE_ROOT))
