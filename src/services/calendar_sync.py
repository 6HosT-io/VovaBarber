"""
Poll Google Calendar for confirmed bookings that have calendar_event_id.

If barber deletes the event in Calendar → cancel in bot + notify client.
If barber moves the event → update date/time in bot + notify client.

Limitation: only bookings created via bot confirm (with stored event id).
Manual-only Calendar events never become bot bookings.
"""
from __future__ import annotations

import asyncio
import os
from loguru import logger
from aiogram import Bot

CHECK_INTERVAL_SEC = int(os.getenv("CALENDAR_SYNC_INTERVAL_SEC", "180"))  # 3 min


def _booking_slot(b: dict) -> str:
    """Best-effort HH:MM from booking fields / comment."""
    for key in ("extracted_time", "slot", "time"):
        v = (b.get(key) or "").strip()
        if v and ":" in v and len(v) <= 5:
            return v
    comment = b.get("comment") or ""
    # comment often "18:30" or "18:30 · note"
    part = comment.split("·")[0].strip()
    if part and ":" in part and len(part) <= 5:
        return part
    return ""


async def sync_once(bot: Bot) -> dict:
    from src.services import settings_store as store
    from src.services import calendar as gcal

    stats = {"checked": 0, "deleted": 0, "moved": 0, "errors": 0}
    if not gcal.is_configured():
        return stats

    bookings = [
        b for b in store.get_confirmed_bookings()
        if b.get("status") == "confirmed" and b.get("calendar_event_id")
    ]
    for b in bookings:
        stats["checked"] += 1
        bid = str(b.get("id"))
        eid = b.get("calendar_event_id")
        user_id = int(b.get("user_id") or 0)
        try:
            ev = gcal.get_event(eid)
            if ev is None:
                # Deleted or cancelled in Calendar
                result = store.cancel_booking(bid, by="calendar")
                if result.get("ok"):
                    stats["deleted"] += 1
                    gcal.invalidate_slots_cache(b.get("date") or "")
                    if user_id:
                        try:
                            old_date = b.get("date") or "—"
                            old_slot = _booking_slot(b) or "—"
                            nl = chr(10)
                            await bot.send_message(
                                user_id,
                                f"❌ Запись отменена барбером.{nl}{nl}"
                                f"Дата: <b>{old_date}</b> · время: <b>{old_slot}</b>{nl}{nl}"
                                "Если нужно другое время — нажмите «Записаться».",
                            )
                        except Exception as e:
                            logger.warning(f"notify client cancel {user_id}: {e}")
                    logger.info(f"Calendar sync: booking {bid} cancelled (event deleted)")
                continue

            new_date, new_time = gcal.event_local_start(ev)
            if not new_date:
                continue
            old_date = (b.get("date") or "").strip()
            old_slot = _booking_slot(b)
            moved = False
            fields = {}
            if new_date and new_date != old_date:
                fields["date"] = new_date
                moved = True
            if new_time and new_time != old_slot:
                # keep comment readable: "HH:MM" or "HH:MM · note"
                comment = b.get("comment") or ""
                if "·" in comment:
                    note = comment.split("·", 1)[1].strip()
                    fields["comment"] = f"{new_time} · {note}" if note else new_time
                elif old_slot and comment.startswith(old_slot):
                    fields["comment"] = new_time + comment[len(old_slot):]
                else:
                    fields["comment"] = new_time
                fields["extracted_time"] = new_time
                moved = True

            if moved and fields:
                store.update_booking(bid, **fields)
                # reset reminders if time/date changed
                store.update_booking(
                    bid,
                    reminder_24h_sent=False,
                    reminder_morning_sent=False,
                    client_confirmed=False,
                    client_thinking=False,
                )
                stats["moved"] += 1
                gcal.invalidate_slots_cache(old_date)
                gcal.invalidate_slots_cache(new_date)
                if user_id:
                    try:
                        nl = chr(10)
                        await bot.send_message(
                            user_id,
                            f"📅 Барбер изменил вашу запись.{nl}{nl}"
                            f"Было: <b>{old_date}</b> · <b>{old_slot or '—'}</b>{nl}"
                            f"Стало: <b>{fields.get('date', old_date)}</b> · "
                            f"<b>{fields.get('extracted_time') or new_time or old_slot or '—'}</b>{nl}{nl}"
                            "Если время не подходит — напишите барберу или перенесите запись.",
                        )
                    except Exception as e:
                        logger.warning(f"notify client move {user_id}: {e}")
                logger.info(f"Calendar sync: booking {bid} moved → {fields}")
        except Exception as e:
            stats["errors"] += 1
            logger.error(f"Calendar sync booking {bid}: {e}")
    return stats


async def calendar_sync_loop(bot: Bot):
    logger.info(f"Calendar sync loop started (every {CHECK_INTERVAL_SEC}s)")
    # small delay so bot is fully up
    await asyncio.sleep(20)
    while True:
        try:
            stats = await sync_once(bot)
            if stats.get("deleted") or stats.get("moved"):
                logger.info(f"Calendar sync: {stats}")
        except Exception as e:
            logger.error(f"Calendar sync loop error: {e}")
        await asyncio.sleep(CHECK_INTERVAL_SEC)
