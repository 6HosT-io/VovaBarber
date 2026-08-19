"""
Google Calendar integration.

Setup: see docs/Google_Calendar_Setup.md
Requires in .env:
  GOOGLE_CALENDAR_ID=primary   # or calendar email/id
  GOOGLE_CREDENTIALS_FILE=config/google_credentials.json
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from loguru import logger

SCOPES = ["https://www.googleapis.com/auth/calendar"]
TIMEZONE = os.getenv("TIMEZONE", "Europe/Riga")


def _credentials_path() -> Path:
    raw = os.getenv("GOOGLE_CREDENTIALS_FILE", "config/google_credentials.json")
    path = Path(raw)
    if not path.is_absolute():
        # project root = parent of src/
        root = Path(__file__).resolve().parent.parent.parent
        path = root / path
    return path


def is_configured() -> bool:
    return _credentials_path().exists() and bool(os.getenv("GOOGLE_CALENDAR_ID"))


def get_calendar_service():
    if not is_configured():
        return None
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        creds = service_account.Credentials.from_service_account_file(
            str(_credentials_path()), scopes=SCOPES
        )
        return build("calendar", "v3", credentials=creds, cache_discovery=False)
    except Exception as e:
        logger.error(f"Google Calendar init failed: {e}")
        return None


def parse_time_from_comment(comment: str) -> Optional[str]:
    """
    Try to extract HH:MM from free text.
    Examples: после 16:00, около 11, в 14:30, 10.00
    Returns 'HH:MM' or None.
    """
    if not comment:
        return None
    # 16:00 or 16.00 or 16-00
    m = re.search(r"\b([01]?\d|2[0-3])[:.\-]([0-5]\d)\b", comment)
    if m:
        return f"{int(m.group(1)):02d}:{m.group(2)}"
    # bare hour: около 11, после 16
    m = re.search(r"\b([01]?\d|2[0-3])\b", comment)
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
    duration_min: int = 45,
    description: str = "",
) -> Optional[str]:
    """
    Create calendar event. date_str: DD/MM/YYYY.
    Start time from comment if found, else 10:00.
    Returns event id or None.
    """
    service = get_calendar_service()
    if not service:
        logger.warning("Calendar not configured — skip event create")
        return None

    base = parse_date_ddmmyyyy(date_str)
    if not base:
        logger.error(f"Bad date for calendar: {date_str}")
        return None

    time_str = parse_time_from_comment(comment) or "10:00"
    hour, minute = map(int, time_str.split(":"))
    start_dt = base.replace(hour=hour, minute=minute, second=0, microsecond=0)
    end_dt = start_dt + timedelta(minutes=duration_min)

    calendar_id = os.getenv("GOOGLE_CALENDAR_ID", "primary")
    body = {
        "summary": summary,
        "description": description or comment,
        "start": {
            "dateTime": start_dt.isoformat(),
            "timeZone": TIMEZONE,
        },
        "end": {
            "dateTime": end_dt.isoformat(),
            "timeZone": TIMEZONE,
        },
    }

    try:
        created = (
            service.events()
            .insert(calendarId=calendar_id, body=body)
            .execute()
        )
        event_id = created.get("id")
        logger.info(f"Calendar event created: {event_id}")
        return event_id
    except Exception as e:
        logger.error(f"Failed to create calendar event: {e}")
        return None


def delete_event(event_id: str) -> bool:
    service = get_calendar_service()
    if not service or not event_id:
        return False
    calendar_id = os.getenv("GOOGLE_CALENDAR_ID", "primary")
    try:
        service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
        logger.info(f"Calendar event deleted: {event_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to delete calendar event: {e}")
        return False
