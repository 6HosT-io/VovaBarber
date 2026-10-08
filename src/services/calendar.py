"""
Google Calendar integration.

Setup: see docs/Google_Calendar_Setup.md

.env:
  GOOGLE_CALENDAR_ID=...          # dedicated Barbershop calendar id (NOT family, ideally not personal mess)
  GOOGLE_CREDENTIALS_FILE=config/google_credentials.json
  TIMEZONE=Europe/Riga

Event colours (Google colorId):
  10 = basil/green  → client bookings
  11 = tomato/red   → blocked / «не работаю»
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Optional

from loguru import logger

SCOPES = ["https://www.googleapis.com/auth/calendar"]
TIMEZONE = os.getenv("TIMEZONE", "Europe/Riga")

# Default day start when client did not specify time
DEFAULT_START = os.getenv("CALENDAR_DEFAULT_START", "08:30")
# Barber plans ~1h per client
DEFAULT_DURATION_MIN = int(os.getenv("CALENDAR_DEFAULT_DURATION_MIN", "30"))
DAY_END = os.getenv("CALENDAR_DAY_END", "21:00")

SLOT_STEP_MIN = int(os.getenv("CALENDAR_SLOT_STEP_MIN", "30"))
# Don't offer a slot starting sooner than this many minutes from now
SLOT_LEAD_MIN = int(os.getenv("CALENDAR_SLOT_LEAD_MIN", "15"))


def get_tz():
    try:
        return ZoneInfo(TIMEZONE)
    except Exception:
        return ZoneInfo("Europe/Riga")


def now_local() -> datetime:
    return datetime.now(get_tz())


COLOR_CLIENT = "10"   # green / basil
COLOR_BLOCK = "11"    # red / tomato
PREFIX_CLIENT = "✂️ "
PREFIX_BLOCK = "🚫 "


def _project_root() -> Path:
    # src/services/calendar.py → repo root
    return Path(__file__).resolve().parent.parent.parent


def _credentials_path() -> Path:
    raw = (os.getenv("GOOGLE_CREDENTIALS_FILE") or "config/google_credentials.json").strip()
    path = Path(raw)
    if path.is_absolute():
        return path
    candidates = [
        _project_root() / path,
        Path.cwd() / path,
        Path("/opt/VovaBarbershopBot") / path,
    ]
    for c in candidates:
        if c.exists():
            return c
    return candidates[0]


def is_configured() -> bool:
    cid = (os.getenv("GOOGLE_CALENDAR_ID") or "").strip().strip('"').strip("'")
    ok = _credentials_path().exists() and bool(cid)
    if not ok:
        logger.warning(
            f"Calendar not configured: creds={_credentials_path()} exists={_credentials_path().exists()} "
            f"GOOGLE_CALENDAR_ID={cid!r}"
        )
    return ok


def get_calendar_id() -> str:
    return (os.getenv("GOOGLE_CALENDAR_ID") or "primary").strip().strip('"').strip("'")


_LAST_INIT_ERROR: str | None = None


def get_calendar_service():
    global _LAST_INIT_ERROR
    _LAST_INIT_ERROR = None
    if not is_configured():
        _LAST_INIT_ERROR = "not configured (missing JSON or GOOGLE_CALENDAR_ID)"
        return None
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        creds = service_account.Credentials.from_service_account_file(
            str(_credentials_path()), scopes=SCOPES
        )
        return build("calendar", "v3", credentials=creds, cache_discovery=False)
    except Exception as e:
        _LAST_INIT_ERROR = f"{type(e).__name__}: {e}"
        logger.error(f"Google Calendar init failed: {_LAST_INIT_ERROR}")
        return None



def diagnose(date_str: str | None = None) -> str:
    """Human-readable status for /test_calendar [DD/MM/YYYY]."""
    lines = []
    path = _credentials_path()
    lines.append(f"credentials path: {path}")
    lines.append(f"credentials exists: {path.exists()}")
    lines.append(f"GOOGLE_CALENDAR_ID: {get_calendar_id()!r}")
    lines.append(f"TIMEZONE: {TIMEZONE}")
    lines.append(
        f"default start: {DEFAULT_START}, duration: {DEFAULT_DURATION_MIN}m, day_end: {DAY_END}"
    )
    if not path.exists():
        lines.append("FAIL: JSON file missing on server")
        return chr(10).join(lines)
    try:
        import json
        data = json.loads(path.read_text())
        lines.append(f"client_email: {data.get('client_email', '?')}")
        lines.append(f"project_id: {data.get('project_id', '?')}")
    except Exception as e:
        lines.append(f"FAIL: cannot read JSON: {e}")
        return chr(10).join(lines)
    svc = get_calendar_service()
    if not svc:
        lines.append("FAIL: could not build Calendar API client")
        if _LAST_INIT_ERROR:
            lines.append(f"error: {_LAST_INIT_ERROR}")
        return chr(10).join(lines)
    try:
        calmeta = svc.calendars().get(calendarId=get_calendar_id()).execute()
        lines.append(f"calendar summary: {calmeta.get('summary')}")
        lines.append(f"calendar access: {calmeta.get('accessRole')}")
        lines.append("OK: API can read this calendar")
    except Exception as e:
        lines.append(f"FAIL: calendars.get: {e}")
        lines.append("Often: wrong Calendar ID, or not shared with client_email")
        return chr(10).join(lines)

    check = (date_str or "").strip() or now_local().strftime("%d/%m/%Y")
    check = check.replace(".", "/")
    lines.append(f"--- slots check for {check} ---")
    invalidate_slots_cache(check)
    try:
        tz = get_tz()
        base = parse_date_ddmmyyyy(check)
        if base:
            day_start = datetime(base.year, base.month, base.day, 0, 0, 0, tzinfo=tz)
            day_end = day_start + timedelta(days=1)
            lines.append(f"timeMin={day_start.isoformat()}")
            lines.append(f"timeMax={day_end.isoformat()}")
    except Exception as e:
        lines.append(f"range build: {e}")

    evs = list_events_for_day(check)
    lines.append(f"raw events from API: {len(evs)}")
    for ev in evs[:15]:
        lines.append(
            f"  • {ev.get('summary')!r} | {ev.get('start')} → {ev.get('end')} | "
            f"color={ev.get('colorId')} block={ev.get('is_block')}"
        )
    busy = get_busy_intervals(check)
    lines.append(f"busy intervals: {len(busy)}")
    for a, b in busy:
        lines.append(f"  • {_fmt_minutes(a)}-{_fmt_minutes(b)}")
    slots = get_available_slots(check, use_cache=False)
    lines.append(
        f"free slots ({len(slots)}): {', '.join(slots[:16])}"
        + ("…" if len(slots) > 16 else "")
    )
    if not evs:
        lines.append(
            "NOTE: 0 events on this day → event may be on another calendar "
            "(primary/Gmail), not this Calendar ID."
        )
    lines.append("--- any events on this calendar (± window) ---")
    upcoming = list_upcoming_events()
    lines.append(f"events in window: {len(upcoming)}")
    if not upcoming:
        lines.append(
            "Calendar «Клиенты» is EMPTY for the bot. "
            "Create event while only «Клиенты» is selected, or use /test_calendar "
            "without date (writes a test event you should see in Google)."
        )
    for ev in upcoming[:12]:
        lines.append(f"  • {ev.get('summary')!r} | {ev.get('start')} → {ev.get('end')}")
    return chr(10).join(lines)


def test_write_event() -> str:
    """Create a short test event and delete it."""
    service = get_calendar_service()
    if not service:
        return "FAIL: service not configured"
    from datetime import datetime as dt
    now = dt.now()
    start = now.replace(second=0, microsecond=0) + timedelta(minutes=5)
    end = start + timedelta(minutes=15)
    body = {
        "summary": "✂️ Bot test — можно удалить",
        "description": "Test from VovaBarbershopBot /test_calendar",
        "colorId": COLOR_CLIENT,
        "start": {"dateTime": start.isoformat(), "timeZone": TIMEZONE},
        "end": {"dateTime": end.isoformat(), "timeZone": TIMEZONE},
    }
    try:
        created = service.events().insert(calendarId=get_calendar_id(), body=body).execute()
        eid = created.get("id")
        service.events().delete(calendarId=get_calendar_id(), eventId=eid).execute()
        return f"OK: create+delete test event id={eid}"
    except Exception as e:
        return f"FAIL write: {e}"


def parse_time_from_comment(comment: str) -> Optional[str]:
    """Extract HH:MM from free text. Returns None if nothing useful."""
    if not comment:
        return None
    m = re.search(r"\b([01]?\d|2[0-3])[:.\-]([0-5]\d)\b", comment)
    if m:
        return f"{int(m.group(1)):02d}:{m.group(2)}"
    m = re.search(
        r"(?:после|около|в|pēc|ap)\s*([01]?\d|2[0-3])\b",
        comment,
        re.I,
    )
    if m:
        return f"{int(m.group(1)):02d}:00"
    return None


def parse_date_ddmmyyyy(date_str: str) -> Optional[datetime]:
    date_str = (date_str or "").strip().replace(".", "/")
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None


def create_event(
    *,
    summary: str,
    date_str: str,
    comment: str = "",
    duration_min: int | None = None,
    description: str = "",
    start_time: str | None = None,
    color: str = COLOR_CLIENT,
) -> Optional[str]:
    """
    Create a *client* booking event (green by default).
    date_str: DD/MM/YYYY
    Start: explicit start_time, else from comment, else DEFAULT_START (08:30).
    Duration: default 30 min (CALENDAR_DEFAULT_DURATION_MIN).
    Returns Google event id or None.
    """
    service = get_calendar_service()
    if not service:
        logger.warning("Calendar not configured — skip event create")
        return None

    base = parse_date_ddmmyyyy(date_str)
    if not base:
        logger.error(f"Bad date for calendar: {date_str}")
        return None

    time_str = start_time or parse_time_from_comment(comment) or DEFAULT_START
    try:
        hour, minute = map(int, time_str.split(":"))
    except Exception:
        hour, minute = 8, 30
    start_dt = base.replace(hour=hour, minute=minute, second=0, microsecond=0)
    dur = duration_min if duration_min is not None else DEFAULT_DURATION_MIN
    end_dt = start_dt + timedelta(minutes=max(15, dur))

    title = summary if summary.startswith(PREFIX_CLIENT) else f"{PREFIX_CLIENT}{summary}"
    body = {
        "summary": title,
        "description": description or comment or "",
        "colorId": color,
        "start": {"dateTime": start_dt.isoformat(), "timeZone": TIMEZONE},
        "end": {"dateTime": end_dt.isoformat(), "timeZone": TIMEZONE},
    }

    try:
        created = (
            service.events()
            .insert(calendarId=get_calendar_id(), body=body)
            .execute()
        )
        event_id = created.get("id")
        logger.info(f"Calendar client event created: {event_id}")
        invalidate_slots_cache(date_str)
        return event_id
    except Exception as e:
        logger.error(f"Failed to create calendar event: {e}")
        return None



def _to_iso_date(date_str: str) -> str | None:
    base = parse_date_ddmmyyyy(date_str)
    if not base:
        return None
    return base.strftime("%Y-%m-%d")


def create_all_day_block(
    start_date: str,
    end_date: str | None = None,
    *,
    title: str = "Не работаю",
    description: str = "Блок из бота (/block или /vacation)",
) -> str | None:
    """
    All-day red event on «Клиенты».
    start_date / end_date: DD/MM/YYYY inclusive.
    Google end.date is exclusive → we add +1 day.
    """
    service = get_calendar_service()
    if not service:
        return None
    start_iso = _to_iso_date(start_date)
    end_inclusive = end_date or start_date
    end_base = parse_date_ddmmyyyy(end_inclusive)
    if not start_iso or not end_base:
        return None
    end_exclusive = (end_base + timedelta(days=1)).strftime("%Y-%m-%d")
    body = {
        "summary": f"{PREFIX_BLOCK}{title}",
        "description": description,
        "colorId": COLOR_BLOCK,
        "start": {"date": start_iso},
        "end": {"date": end_exclusive},
    }
    try:
        created = (
            service.events()
            .insert(calendarId=get_calendar_id(), body=body)
            .execute()
        )
        eid = created.get("id")
        logger.info(f"Calendar all-day block: {eid} {start_iso}→{end_exclusive}")
        invalidate_slots_cache()
        return eid
    except Exception as e:
        logger.error(f"create_all_day_block failed: {e}")
        return None


def create_block_event(
    *,
    date_str: str,
    start_time: str,
    end_time: str,
    title: str = "Не работаю",
) -> Optional[str]:
    """
    Red «unavailable» block on the same Barbershop calendar.
    date_str DD/MM/YYYY, times HH:MM.
    """
    service = get_calendar_service()
    if not service:
        return None
    base = parse_date_ddmmyyyy(date_str)
    if not base:
        return None
    try:
        sh, sm = map(int, start_time.split(":"))
        eh, em = map(int, end_time.split(":"))
    except Exception:
        logger.error(f"Bad block times: {start_time}-{end_time}")
        return None
    start_dt = base.replace(hour=sh, minute=sm, second=0, microsecond=0)
    end_dt = base.replace(hour=eh, minute=em, second=0, microsecond=0)
    if end_dt <= start_dt:
        end_dt += timedelta(days=1)

    body = {
        "summary": f"{PREFIX_BLOCK}{title}",
        "description": "Blocked via barbershop bot / calendar",
        "colorId": COLOR_BLOCK,
        "start": {"dateTime": start_dt.isoformat(), "timeZone": TIMEZONE},
        "end": {"dateTime": end_dt.isoformat(), "timeZone": TIMEZONE},
    }
    try:
        created = (
            service.events()
            .insert(calendarId=get_calendar_id(), body=body)
            .execute()
        )
        eid = created.get("id")
        logger.info(f"Calendar block event created: {eid}")
        invalidate_slots_cache(date_str)
        return eid
    except Exception as e:
        logger.error(f"Failed to create block event: {e}")
        return None



def list_upcoming_events(days_back: int = 7, days_forward: int = 60, limit: int = 30) -> list[dict]:
    """Any events on the connected calendar in a wide window (debug empty-day cases)."""
    service = get_calendar_service()
    if not service:
        return []
    tz = get_tz()
    now = now_local()
    time_min = (now - timedelta(days=days_back)).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    time_max = (now + timedelta(days=days_forward)).replace(hour=23, minute=59, second=59, microsecond=0).isoformat()
    items: list = []
    page_token = None
    try:
        while True:
            kwargs = dict(
                calendarId=get_calendar_id(),
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy="startTime",
                timeZone=TIMEZONE,
                maxResults=100,
            )
            if page_token:
                kwargs["pageToken"] = page_token
            result = service.events().list(**kwargs).execute()
            items.extend(result.get("items") or [])
            page_token = result.get("nextPageToken")
            if not page_token:
                break
    except Exception as e:
        logger.error(f"list_upcoming_events: {e}")
        return []
    out = []
    for ev in items[:limit]:
        summary = ev.get("summary") or ""
        start = (ev.get("start") or {}).get("dateTime") or (ev.get("start") or {}).get("date")
        end = (ev.get("end") or {}).get("dateTime") or (ev.get("end") or {}).get("date")
        out.append({"summary": summary, "start": start, "end": end, "id": ev.get("id")})
    return out


def list_events_for_day(date_str: str) -> list[dict]:
    """
    All events on the Barbershop calendar for one day.
    Paginates with pageToken until complete.
    Returns list of {id, summary, start, end, colorId, is_block}.
    """
    service = get_calendar_service()
    if not service:
        return []
    base = parse_date_ddmmyyyy(date_str)
    if not base:
        return []
    # Google requires RFC3339 with mandatory timezone offset on timeMin/timeMax
    try:
        tz = ZoneInfo(TIMEZONE)
    except Exception:
        tz = ZoneInfo("Europe/Riga")
    day_start = datetime(base.year, base.month, base.day, 0, 0, 0, tzinfo=tz)
    day_end = day_start + timedelta(days=1)
    time_min = day_start.isoformat()
    time_max = day_end.isoformat()

    items: list = []
    page_token = None
    try:
        while True:
            kwargs = dict(
                calendarId=get_calendar_id(),
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy="startTime",
                timeZone=TIMEZONE,
                maxResults=100,
            )
            if page_token:
                kwargs["pageToken"] = page_token
            result = service.events().list(**kwargs).execute()
            items.extend(result.get("items") or [])
            page_token = result.get("nextPageToken")
            if not page_token:
                break
    except Exception as e:
        logger.error(f"list_events_for_day: {e}")
        return []

    out = []
    for ev in items:
        summary = ev.get("summary") or ""
        start = (ev.get("start") or {}).get("dateTime") or (ev.get("start") or {}).get("date")
        end = (ev.get("end") or {}).get("dateTime") or (ev.get("end") or {}).get("date")
        color = str(ev.get("colorId") or "")
        low = summary.lower()
        is_block = (
            color == COLOR_BLOCK
            or summary.startswith(PREFIX_BLOCK)
            or "не работаю" in low
            or "ne strādāju" in low
            or "blocked" in low
            or "unavailable" in low
        )
        out.append(
            {
                "id": ev.get("id"),
                "summary": summary,
                "start": start,
                "end": end,
                "colorId": color,
                "is_block": is_block,
            }
        )
    return out



def get_event(event_id: str) -> dict | None:
    """
    Fetch one event by id. Returns None if missing/deleted/404.
    Keys: id, summary, start, end, status (incl. cancelled).
    """
    service = get_calendar_service()
    if not service or not event_id:
        return None
    try:
        ev = (
            service.events()
            .get(calendarId=get_calendar_id(), eventId=event_id)
            .execute()
        )
        if (ev.get("status") or "").lower() == "cancelled":
            return None
        start = (ev.get("start") or {}).get("dateTime") or (ev.get("start") or {}).get("date")
        end = (ev.get("end") or {}).get("dateTime") or (ev.get("end") or {}).get("date")
        return {
            "id": ev.get("id"),
            "summary": ev.get("summary") or "",
            "start": start,
            "end": end,
            "status": ev.get("status"),
            "raw": ev,
        }
    except Exception as e:
        err = str(e).lower()
        if "404" in err or "not found" in err or "deleted" in err:
            logger.info(f"Calendar event gone: {event_id}")
            return None
        logger.warning(f"get_event {event_id}: {e}")
        return None


def event_local_start(ev: dict) -> tuple[str | None, str | None]:
    """Return (DD/MM/YYYY, HH:MM) in bot TIMEZONE, or (date, None) for all-day."""
    start_raw = (ev or {}).get("start") or ""
    if not start_raw:
        return None, None
    if "T" not in str(start_raw):
        # all-day YYYY-MM-DD
        try:
            y, m, d = str(start_raw)[:10].split("-")
            return f"{d}/{m}/{y}", None
        except Exception:
            return None, None
    try:
        tz = get_tz()
        st = str(start_raw).replace("Z", "+00:00")
        start_dt = datetime.fromisoformat(st)
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=tz)
        local = start_dt.astimezone(tz)
        return local.strftime("%d/%m/%Y"), local.strftime("%H:%M")
    except Exception as e:
        logger.warning(f"event_local_start: {e}")
        return None, None


def delete_event(event_id: str) -> bool:
    service = get_calendar_service()
    if not service or not event_id:
        return False
    try:
        service.events().delete(
            calendarId=get_calendar_id(), eventId=event_id
        ).execute()
        logger.info(f"Calendar event deleted: {event_id}")
        invalidate_slots_cache()
        return True
    except Exception as e:
        logger.error(f"Failed to delete calendar event: {e}")
        return False


def _parse_hhmm(s: str) -> tuple[int, int]:
    parts = (s or "08:30").strip().split(":")
    return int(parts[0]), int(parts[1]) if len(parts) > 1 else 0


def _minutes(h: int, m: int) -> int:
    return h * 60 + m


def _fmt_minutes(total: int) -> str:
    return f"{total // 60:02d}:{total % 60:02d}"


def _event_to_minutes(ev: dict, day_base: datetime) -> tuple[int, int] | None:
    """Return (start_min, end_min) in local TIMEZONE minutes from midnight."""
    start_raw = ev.get("start") or ""
    end_raw = ev.get("end") or ""
    if not start_raw:
        return None
    # all-day: YYYY-MM-DD → whole day busy
    if "T" not in str(start_raw):
        return 0, 24 * 60
    try:
        try:
            tz = ZoneInfo(TIMEZONE)
        except Exception:
            tz = ZoneInfo("Europe/Riga")
        st = str(start_raw).replace("Z", "+00:00")
        en = str(end_raw or start_raw).replace("Z", "+00:00")
        start_dt = datetime.fromisoformat(st)
        end_dt = datetime.fromisoformat(en)
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=tz)
        if end_dt.tzinfo is None:
            end_dt = end_dt.replace(tzinfo=tz)
        start_local = start_dt.astimezone(tz)
        end_local = end_dt.astimezone(tz)
        sm = start_local.hour * 60 + start_local.minute
        em = end_local.hour * 60 + end_local.minute
        # multi-day timed: clamp to this local day
        day0 = datetime(day_base.year, day_base.month, day_base.day, tzinfo=tz)
        if start_local.date() < day0.date():
            sm = 0
        if end_local.date() > day0.date():
            em = 24 * 60
        if em <= sm:
            em = sm + DEFAULT_DURATION_MIN
        return sm, em
    except Exception as e:
        logger.warning(f"event parse: {e} {start_raw}")
        return None


def get_busy_intervals(date_str: str) -> list[tuple[int, int]]:
    """Busy (start_min, end_min) from Google Calendar for the day. Includes manual + bot events."""
    events = list_events_for_day(date_str)
    base = parse_date_ddmmyyyy(date_str)
    if not base:
        return []
    busy = []
    for ev in events:
        pair = _event_to_minutes(ev, base)
        if pair:
            busy.append(pair)
            logger.info(
                f"busy {date_str}: {ev.get('summary')!r} "
                f"{_fmt_minutes(pair[0])}-{_fmt_minutes(pair[1])}"
            )
    if not events:
        logger.info(f"busy {date_str}: no events from Calendar API")
    busy.sort()
    merged: list[list[int]] = []
    for s, e in busy:
        if not merged or s > merged[-1][1]:
            merged.append([s, e])
        else:
            merged[-1][1] = max(merged[-1][1], e)
    return [(a, b) for a, b in merged]


def _slot_fits(start_m: int, dur: int, busy: list[tuple[int, int]], day_end_m: int) -> bool:
    end_m = start_m + dur
    if end_m > day_end_m:
        return False
    for bs, be in busy:
        if start_m < be and end_m > bs:
            return False
    return True


def _adjacency_score(start_m: int, dur: int, busy: list[tuple[int, int]]) -> int:
    """
    Higher = better.
      exactly before client +2000, exactly after +2000,
      small hole ≤ duration +1500, near ≤60min +800.
      empty day: prefer earlier (handled in sort by time).
    """
    end_m = start_m + dur
    if not busy:
        return 0
    score = 0
    for bs, be in busy:
        if end_m == bs:
            score += 2000
        if start_m == be:
            score += 2000
        gap_before = bs - end_m
        gap_after = start_m - be
        if 0 < gap_before <= dur:
            score += 1500
        if 0 < gap_after <= dur:
            score += 1500
        if 0 < gap_before <= 60 or 0 < gap_after <= 60:
            score += 800
        dist = min(abs(start_m - be), abs(end_m - bs), abs(start_m - bs), abs(end_m - be))
        score -= min(dist, 480) // 15
    return score



# Short TTL cache: avoid hammering Calendar when client flips day/back
_slots_cache: dict[str, tuple[float, list[str]]] = {}
_SLOTS_CACHE_TTL = float(os.getenv("CALENDAR_SLOTS_CACHE_TTL", "45"))


def invalidate_slots_cache(date_str: str | None = None):
    if date_str is None:
        _slots_cache.clear()
    else:
        _slots_cache.pop(date_str, None)


def get_available_slots(
    date_str: str,
    *,
    duration_min: int | None = None,
    day_start: str | None = None,
    day_end: str | None = None,
    step_min: int | None = None,
    limit: int = 48,
    use_cache: bool = True,
) -> list[str]:
    """
    Free HH:MM starts for the day, prioritized next to existing calendar events.
    Any event on calendar «Клиенты» (client, manual, «Не работаю») blocks time.
    """
    import time as _time
    cache_key = date_str
    if use_cache and cache_key in _slots_cache:
        ts, cached = _slots_cache[cache_key]
        if _time.time() - ts < _SLOTS_CACHE_TTL:
            return list(cached)

    dur = duration_min if duration_min is not None else DEFAULT_DURATION_MIN
    step = step_min if step_min is not None else SLOT_STEP_MIN
    sh, sm = _parse_hhmm(day_start or DEFAULT_START)
    eh, em = _parse_hhmm(day_end or DAY_END)
    day_start_m = _minutes(sh, sm)
    day_end_m = _minutes(eh, em)

    busy = get_busy_intervals(date_str)
    candidates = []
    cursor = day_start_m
    # For "today": do not offer slots that already started (lead time buffer)
    min_start_m = day_start_m
    base_day = parse_date_ddmmyyyy(date_str)
    if base_day:
        nl = now_local()
        if nl.year == base_day.year and nl.month == base_day.month and nl.day == base_day.day:
            min_start_m = max(
                day_start_m,
                nl.hour * 60 + nl.minute + SLOT_LEAD_MIN,
            )
    while cursor + dur <= day_end_m:
        if cursor >= min_start_m and _slot_fits(cursor, dur, busy, day_end_m):
            score = _adjacency_score(cursor, dur, busy)
            candidates.append((score, cursor))
        cursor += step
    # Chronological order for clients (adjacency score kept for future ranking if needed)
    candidates.sort(key=lambda x: x[1])
    out = [_fmt_minutes(m) for _, m in candidates[:limit]]

    _slots_cache[cache_key] = (_time.time(), list(out))
    return out


def slots_keyboard_rows(slots: list[str], prefix: str = "slot") -> list[list[str]]:
    return slots


    """Helper: chunk slot times for buttons (values only)."""
    return slots


def day_is_bookable(date_str: str) -> tuple[bool, str]:
    """
    (ok, reason_code)
    reason_code: ok | blocked | no_slots | past
    Uses bot blocks + live calendar slots (respects "now" for today).
    """
    try:
        from src.services import settings_store as store
        if store.is_blocked(date_str):
            return False, "blocked"
    except Exception:
        pass
    slots = get_available_slots(date_str, use_cache=True)
    if not slots:
        base = parse_date_ddmmyyyy(date_str)
        if base:
            nl = now_local()
            if (nl.year, nl.month, nl.day) == (base.year, base.month, base.day):
                return False, "past"
        return False, "no_slots"
    return True, "ok"
