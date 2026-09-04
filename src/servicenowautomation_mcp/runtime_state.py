"""Runtime state helpers for startup and request diagnostics."""

from __future__ import annotations

import os
import socket
from datetime import UTC, datetime
from typing import Any

_PROCESS_STARTED_AT = datetime.now(UTC)
_runtime_state: dict[str, Any] = {
    "lifespan_started": False,
    "lifespan_start_count": 0,
    "lifespan_last_started_at": None,
    "lifespan_last_stopped_at": None,
    "lifespan_server_type": None,
}


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def mark_lifespan_started(server: Any) -> None:
    _runtime_state["lifespan_started"] = True
    _runtime_state["lifespan_start_count"] += 1
    _runtime_state["lifespan_last_started_at"] = _utc_now()
    _runtime_state["lifespan_server_type"] = type(server).__name__


def mark_lifespan_stopped() -> None:
    _runtime_state["lifespan_started"] = False
    _runtime_state["lifespan_last_stopped_at"] = _utc_now()


def snapshot_runtime_state() -> dict[str, Any]:
    return {
        "process_id": os.getpid(),
        "hostname": socket.gethostname(),
        "process_started_at": _PROCESS_STARTED_AT.isoformat(),
        **_runtime_state,
    }
