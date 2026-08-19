"""
Runtime settings store.
Reads defaults from config/*.yaml and allows overrides saved to config/runtime_settings.yaml
"""
from pathlib import Path
from typing import Any
import yaml
from loguru import logger

BASE = Path("config")
RUNTIME_FILE = BASE / "runtime_settings.yaml"


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _save_yaml(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)


def get_runtime() -> dict:
    return _load_yaml(RUNTIME_FILE)


def save_runtime(data: dict):
    _save_yaml(RUNTIME_FILE, data)
    logger.info("Runtime settings saved")


def get_services() -> list:
    runtime = get_runtime()
    if "services" in runtime:
        return runtime["services"]
    data = _load_yaml(BASE / "services.yaml")
    return data.get("services", [])


def save_services(services: list):
    runtime = get_runtime()
    runtime["services"] = services
    save_runtime(runtime)


def get_location() -> str:
    runtime = get_runtime()
    if "location" in runtime:
        return runtime["location"]
    data = _load_yaml(BASE / "settings.yaml")
    return data.get("location", "Jasmuižas iela 9, Rīga")


def save_location(location: str):
    runtime = get_runtime()
    runtime["location"] = location
    save_runtime(runtime)


def get_working_hours() -> dict:
    runtime = get_runtime()
    if "working_hours" in runtime:
        return runtime["working_hours"]
    data = _load_yaml(BASE / "settings.yaml")
    return data.get("working_hours", {})


def save_working_hours(hours: dict):
    runtime = get_runtime()
    runtime["working_hours"] = hours
    save_runtime(runtime)


def get_welcome_text(lang: str = "ru") -> str:
    runtime = get_runtime()
    key = f"welcome_{lang}"
    if key in runtime:
        return runtime[key]
    if lang == "lv":
        return (
            "Reģistrējieties pie labākā bārddziņa, friziera un drauga — bez zvaniem un gaidīšanas!\n\n"
            "🗓️ Izvēlieties dienu (šodien / rīt / parīt)\n"
            "⌚️ Norādiet jums ērtu laiku\n"
            "💇 Izvēlieties pakalpojumu\n"
            "☑️ Saņemiet apstiprinājumu no bārddziņa\n\n"
            "💈 Adrese: Jasmuižas iela 9, Rīga\n"
            "Valodas: krievu un latviešu\n\n"
            "Vienkārši nospiediet Start un izvēlieties to, kas jums ir aktuāli.\n\n"
            "Svarīgi: bots nosūta atgādinājumus 24 stundas pirms rezervācijas un tajā pašā dienā. "
            "Ja apstiprināsiet pirmo reizi, tajā pašā rītā atgādinājums netiks nosūtīts."
        )
    return (
        "Запись к Лучшему Барберу, Парикмахеру и Другу — без звонков и ожидания!\n\n"
        "🗓️ Выберите день (сегодня / завтра / послезавтра)\n"
        "⌚️ Укажите удобное время\n"
        "💇 Выберите услугу\n"
        "☑️ Получите подтверждение от барбера\n\n"
        "💈 Адрес: Jasmuižas iela 9, Rīga\n"
        "Языки: русский и латышский\n\n"
        "Просто нажмите Start и выбирайте, что актуально.\n\n"
        "Важно: бот отправляет напоминания за 24 часа до записи и в тот же день. "
        "Если подтвердите в первый раз — утром того же дня оповещения не будет."
    )


def save_welcome_text(lang: str, text: str):
    runtime = get_runtime()
    runtime[f"welcome_{lang}"] = text
    save_runtime(runtime)


def get_reminder_texts() -> dict:
    runtime = get_runtime()
    return {
        "reminder_24h_ru": runtime.get(
            "reminder_24h_ru",
            "Привет! ✂️ Напоминаем про вашу запись. Всё в силе?",
        ),
        "reminder_24h_lv": runtime.get(
            "reminder_24h_lv",
            "Sveiki! ✂️ Atgādinām par jūsu pierakstu. Vai viss spēkā?",
        ),
        "reminder_morning_ru": runtime.get(
            "reminder_morning_ru",
            "Доброе утро! ✂️ Сегодня у вас запись. Ждём вас!",
        ),
        "reminder_morning_lv": runtime.get(
            "reminder_morning_lv",
            "Labrīt! ✂️ Šodien jums ir pieraksts. Gaidām jūs!",
        ),
    }


def save_reminder_text(key: str, text: str):
    runtime = get_runtime()
    runtime[key] = text
    save_runtime(runtime)


def format_services_text(lang: str = "ru") -> str:
    services = get_services()
    lines = []
    for s in services:
        if not s.get("is_active", True):
            continue
        name = s.get("name_ru") if lang == "ru" else s.get("name_lv")
        price = s.get("price", "?")
        dur = s.get("duration_min", "?")
        lines.append(f"• {name} — <b>{price} €</b> (~{dur} мин)")
    return "\n".join(lines) if lines else "Услуги не заданы"


def format_hours_text() -> str:
    hours = get_working_hours()
    lines = []
    wd = hours.get("weekdays", [])
    if wd:
        parts = [f"{x['start']}–{x['end']}" for x in wd]
        lines.append("Пн–Пт: " + ", ".join(parts))
    sat = hours.get("saturday", [])
    if sat:
        parts = [f"{x['start']}–{x['end']}" for x in sat]
        lines.append("Сб: " + ", ".join(parts))
    sun = hours.get("sunday", [])
    if not sun:
        lines.append("Вс: выходной")
    else:
        parts = [f"{x['start']}–{x['end']}" for x in sun]
        lines.append("Вс: " + ", ".join(parts))
    return "\n".join(lines) if lines else "Часы не заданы"


# ---------- Client contact names (barber's nicknames) ----------

def get_client_names() -> dict:
    """telegram_id (str) -> custom name"""
    runtime = get_runtime()
    return runtime.get("client_names", {}) or {}


def get_client_contact_name(telegram_id: int):
    return get_client_names().get(str(telegram_id))


def save_client_contact_name(telegram_id: int, name: str):
    runtime = get_runtime()
    names = runtime.get("client_names", {}) or {}
    names[str(telegram_id)] = name.strip()
    runtime["client_names"] = names
    save_runtime(runtime)


def format_client_line(telegram_id: int, tg_full_name) -> str:
    """Line for group messages: Telegram name + optional contact name + last services."""
    tg = tg_full_name or "Клиент"
    contact = get_client_contact_name(telegram_id)
    last = format_last_services_line(telegram_id, limit=3)
    if contact:
        return f"👤 {tg}\n📱 В контактах: <b>{contact}</b>\n🗂 {last}"
    return f"👤 {tg}\n🗂 {last}"


# ---------- Blocked days (persist) ----------

def get_blocked_days() -> set:
    runtime = get_runtime()
    days = runtime.get("blocked_days", []) or []
    return set(days)


def is_blocked(date_str: str) -> bool:
    """date_str in DD/MM/YYYY"""
    return date_str in get_blocked_days()


def block_day(date_str: str):
    runtime = get_runtime()
    days = set(runtime.get("blocked_days", []) or [])
    days.add(date_str)
    runtime["blocked_days"] = sorted(days)
    save_runtime(runtime)


def unblock_day(date_str: str):
    runtime = get_runtime()
    days = set(runtime.get("blocked_days", []) or [])
    days.discard(date_str)
    runtime["blocked_days"] = sorted(days)
    save_runtime(runtime)


def block_range(start_str: str, end_str: str):
    from datetime import datetime, timedelta
    start = datetime.strptime(start_str, "%d/%m/%Y").date()
    end = datetime.strptime(end_str, "%d/%m/%Y").date()
    runtime = get_runtime()
    days = set(runtime.get("blocked_days", []) or [])
    cur = start
    while cur <= end:
        days.add(cur.strftime("%d/%m/%Y"))
        cur += timedelta(days=1)
    runtime["blocked_days"] = sorted(days)
    save_runtime(runtime)


def unblock_range(start_str: str, end_str: str) -> int:
    """Remove blocks from start to end inclusive. Returns number of days removed."""
    from datetime import datetime, timedelta
    start = datetime.strptime(start_str, "%d/%m/%Y").date()
    end = datetime.strptime(end_str, "%d/%m/%Y").date()
    runtime = get_runtime()
    days = set(runtime.get("blocked_days", []) or [])
    removed = 0
    cur = start
    while cur <= end:
        key = cur.strftime("%d/%m/%Y")
        if key in days:
            days.discard(key)
            removed += 1
        cur += timedelta(days=1)
    runtime["blocked_days"] = sorted(days)
    save_runtime(runtime)
    return removed


def clear_all_blocked() -> int:
    runtime = get_runtime()
    count = len(runtime.get("blocked_days", []) or [])
    runtime["blocked_days"] = []
    save_runtime(runtime)
    return count


# ---------- Pending bookings (for confirm → calendar) ----------

def save_pending_booking(user_id: int, date_str: str, comment: str, client_name: str = ""):
    runtime = get_runtime()
    pending = runtime.get("pending_bookings", {}) or {}
    pending[str(user_id)] = {
        "date": date_str,
        "comment": comment,
        "client_name": client_name,
    }
    runtime["pending_bookings"] = pending
    save_runtime(runtime)


def pop_pending_booking(user_id: int) -> dict | None:
    runtime = get_runtime()
    pending = runtime.get("pending_bookings", {}) or {}
    data = pending.pop(str(user_id), None)
    runtime["pending_bookings"] = pending
    save_runtime(runtime)
    return data


# ---------- Client service history ----------

def add_service_history(user_id: int, service_text: str, date_str: str = "", booking_id: str = ""):
    """Append a service visit for the client (newest last). Only active entries count."""
    runtime = get_runtime()
    history = runtime.get("service_history", {}) or {}
    key = str(user_id)
    entries = history.get(key, [])
    if not isinstance(entries, list):
        entries = []
    entries.append({
        "service": (service_text or "").strip() or "—",
        "date": date_str or "",
        "booking_id": booking_id or "",
        "status": "active",
    })
    history[key] = entries[-20:]
    runtime["service_history"] = history
    save_runtime(runtime)


def cancel_service_history(user_id: int, booking_id: str = "", date_str: str = ""):
    """Mark matching history entries as cancelled so they leave «last services»."""
    runtime = get_runtime()
    history = runtime.get("service_history", {}) or {}
    key = str(user_id)
    entries = history.get(key, [])
    if not isinstance(entries, list):
        return
    for e in entries:
        if e.get("status") == "cancelled":
            continue
        if booking_id and e.get("booking_id") == booking_id:
            e["status"] = "cancelled"
        elif not booking_id and date_str and e.get("date") == date_str:
            e["status"] = "cancelled"
            break  # cancel latest match for that date
    # if no booking_id and no date — cancel the newest active
    if not booking_id and not date_str:
        for e in reversed(entries):
            if e.get("status", "active") != "cancelled":
                e["status"] = "cancelled"
                break
    history[key] = entries
    runtime["service_history"] = history
    save_runtime(runtime)


def get_last_services(user_id: int, limit: int = 3) -> list:
    """Return last N *active* services, newest first."""
    runtime = get_runtime()
    history = runtime.get("service_history", {}) or {}
    entries = history.get(str(user_id), [])
    if not isinstance(entries, list):
        return []
    active = [e for e in entries if e.get("status", "active") != "cancelled"]
    return list(reversed(active[-limit:]))


def format_last_services_line(user_id: int, limit: int = 3) -> str:
    items = get_last_services(user_id, limit=limit)
    if not items:
        return "Last time used services: —"
    parts = []
    for e in items:
        svc = e.get("service", "—")
        dt = e.get("date", "")
        if dt:
            parts.append(f"{svc} ({dt})")
        else:
            parts.append(svc)
    return "Last time used services: " + "; ".join(parts)


# ---------- Confirmed bookings (for reminders) ----------

def _new_booking_id() -> str:
    import time
    return str(int(time.time() * 1000))


def add_confirmed_booking(
    user_id: int,
    date_str: str,
    comment: str,
    client_name: str = "",
) -> str:
    runtime = get_runtime()
    bookings = runtime.get("confirmed_bookings", []) or []
    bid = _new_booking_id()
    bookings.append({
        "id": bid,
        "user_id": user_id,
        "date": date_str,
        "comment": comment,
        "client_name": client_name,
        "status": "confirmed",
        "reminder_24h_sent": False,
        "reminder_morning_sent": False,
        "client_confirmed": False,
        "client_thinking": False,
    })
    runtime["confirmed_bookings"] = bookings[-200:]
    save_runtime(runtime)
    return bid


def cancel_booking(booking_id: str, by: str = "barber") -> dict | None:
    """Cancel booking; remove from history; stop reminders. by: barber|client"""
    b = update_booking(booking_id, status=f"cancelled_by_{by}")
    if not b:
        return None
    cancel_service_history(int(b["user_id"]), booking_id=booking_id, date_str=b.get("date", ""))
    return b


def get_active_bookings_for_user(user_id: int) -> list:
    return [
        b for b in get_confirmed_bookings()
        if int(b.get("user_id", 0)) == int(user_id)
        and b.get("status") == "confirmed"
    ]


def get_confirmed_bookings() -> list:
    runtime = get_runtime()
    return list(runtime.get("confirmed_bookings", []) or [])


def update_booking(booking_id: str, **fields) -> dict | None:
    runtime = get_runtime()
    bookings = runtime.get("confirmed_bookings", []) or []
    found = None
    for b in bookings:
        if str(b.get("id")) == str(booking_id):
            b.update(fields)
            found = b
            break
    runtime["confirmed_bookings"] = bookings
    save_runtime(runtime)
    return found


def mark_reminder_sent(booking_id: str, kind: str):
    if kind == "24h":
        update_booking(booking_id, reminder_24h_sent=True)
    elif kind == "morning":
        update_booking(booking_id, reminder_morning_sent=True)


def get_booking(booking_id: str) -> dict | None:
    for b in get_confirmed_bookings():
        if str(b.get("id")) == str(booking_id):
            return b
    return None
