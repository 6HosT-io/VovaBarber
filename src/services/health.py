"""Lightweight runtime health for /status and /ping."""
from __future__ import annotations

import time
from typing import Any

_started_at: float | None = None
_last_update_at: float | None = None
_last_update_type: str = ""
_last_reminder_at: float | None = None
_last_sync_at: float | None = None
_last_sync_note: str = ""
_last_error: str = ""
_mode: str = "long_polling"


def mark_started(mode: str = "long_polling") -> None:
    global _started_at, _mode
    _started_at = time.time()
    _mode = mode or "long_polling"


def mark_update(update_type: str = "") -> None:
    global _last_update_at, _last_update_type
    _last_update_at = time.time()
    _last_update_type = update_type or ""


def mark_reminder_tick() -> None:
    global _last_reminder_at
    _last_reminder_at = time.time()


def mark_sync_tick(note: str = "") -> None:
    global _last_sync_at, _last_sync_note
    _last_sync_at = time.time()
    _last_sync_note = note or ""


def mark_error(msg: str) -> None:
    global _last_error
    _last_error = (msg or "")[:300]


def _ago(ts: float | None) -> str:
    if not ts:
        return "never"
    sec = max(0, int(time.time() - ts))
    if sec < 60:
        return f"{sec}s ago"
    if sec < 3600:
        return f"{sec // 60}m {sec % 60}s ago"
    h = sec // 3600
    m = (sec % 3600) // 60
    return f"{h}h {m}m ago"


def snapshot() -> dict[str, Any]:
    return {
        "mode": _mode,
        "started_at": _started_at,
        "uptime_sec": int(time.time() - _started_at) if _started_at else None,
        "last_update_at": _last_update_at,
        "last_update_type": _last_update_type,
        "last_update_ago": _ago(_last_update_at),
        "last_reminder_at": _last_reminder_at,
        "last_reminder_ago": _ago(_last_reminder_at),
        "last_sync_at": _last_sync_at,
        "last_sync_ago": _ago(_last_sync_at),
        "last_sync_note": _last_sync_note,
        "last_error": _last_error,
    }


def format_uptime(sec: int | None) -> str:
    if sec is None:
        return "—"
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m}m"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"
