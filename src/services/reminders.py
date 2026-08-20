"""
Reminder scheduler: 24h before + morning of appointment day.

Rules:
- 24h reminder: once when ~20–28 hours remain until appointment
- Morning reminder: on appointment day after 08:00 local, if client did NOT
  press «Да, буду» on the 24h message
- Buttons: Да буду / Подумаю / Нужно перенести
"""
from __future__ import annotations

import asyncio
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from loguru import logger

from src.services import settings_store as store
from src.services.calendar import parse_time_from_comment, parse_date_ddmmyyyy

TIMEZONE = ZoneInfo(os.getenv("TIMEZONE", "Europe/Riga"))
CHECK_INTERVAL_SEC = 120  # every 2 minutes


def _appointment_dt(date_str: str, comment: str) -> datetime | None:
    base = parse_date_ddmmyyyy(date_str)
    if not base:
        return None
    time_str = parse_time_from_comment(comment) or "10:00"
    hour, minute = map(int, time_str.split(":"))
    return base.replace(hour=hour, minute=minute, second=0, microsecond=0, tzinfo=TIMEZONE)


def reminder_keyboard(booking_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, буду", callback_data=f"rem:yes:{booking_id}"),
            InlineKeyboardButton(text="🤔 Подумаю", callback_data=f"rem:think:{booking_id}"),
        ],
        [
            InlineKeyboardButton(text="📅 Нужно перенести", callback_data=f"rem:move:{booking_id}"),
        ],
    ])


def _texts(lang: str = "ru") -> dict:
    t = store.get_reminder_texts()
    if lang == "lv":
        return {
            "24h": t.get("reminder_24h_lv") or t.get("reminder_24h_ru"),
            "morning": t.get("reminder_morning_lv") or t.get("reminder_morning_ru"),
        }
    return {
        "24h": t.get("reminder_24h_ru"),
        "morning": t.get("reminder_morning_ru"),
    }


async def _send_reminder(bot: Bot, booking: dict, kind: str):
    """kind: '24h' or 'morning'"""
    user_id = int(booking["user_id"])
    booking_id = booking["id"]
    date_str = booking.get("date", "")
    comment = booking.get("comment", "")
    appt = _appointment_dt(date_str, comment)
    time_part = appt.strftime("%H:%M") if appt else ""
    when = f"{date_str}" + (f", <b>{time_part}</b>" if time_part else "")

    lang = "ru"  # could store per-user later
    base = _texts(lang)[kind]
    if kind == "24h":
        body = (
            f"{base}\n\n"
            f"📅 Запись: {when}\n"
            f"💬 {comment}\n\n"
            f"Подтвердите, пожалуйста:"
        )
    else:
        body = (
            f"{base}\n\n"
            f"📅 Сегодня: {when}\n"
            f"💬 {comment}\n\n"
            f"Всё в силе?"
        )

    try:
        await bot.send_message(
            user_id,
            body,
            reply_markup=reminder_keyboard(booking_id),
        )
        if kind == "24h":
            store.mark_reminder_sent(booking_id, "24h")
        else:
            store.mark_reminder_sent(booking_id, "morning")
        logger.info(f"Reminder {kind} sent to {user_id} booking={booking_id}")
    except Exception as e:
        logger.error(f"Failed reminder {kind} to {user_id}: {e}")


async def check_and_send(bot: Bot):
    now = datetime.now(TIMEZONE)
    bookings = store.get_confirmed_bookings()

    for b in bookings:
        if b.get("status") != "confirmed":
            continue
        appt = _appointment_dt(b.get("date", ""), b.get("comment", ""))
        if not appt:
            continue
        # skip past appointments
        if appt < now - timedelta(hours=1):
            continue

        delta = appt - now
        hours = delta.total_seconds() / 3600

        # --- 24h window: 20–28 hours before ---
        if not b.get("reminder_24h_sent") and 20 <= hours <= 28:
            await _send_reminder(bot, b, "24h")
            continue

        # --- Morning: same calendar day, after 08:00, before appointment ---
        if (
            not b.get("reminder_morning_sent")
            and not b.get("client_confirmed")  # «Да, буду» skips morning
            and appt.date() == now.date()
            and now.hour >= 8
            and now < appt
        ):
            await _send_reminder(bot, b, "morning")


async def reminder_loop(bot: Bot):
    logger.info("Reminder loop started")
    while True:
        try:
            await check_and_send(bot)
        except Exception as e:
            logger.error(f"Reminder loop error: {e}")
        await asyncio.sleep(CHECK_INTERVAL_SEC)
