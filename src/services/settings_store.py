"""
Runtime settings store.
Reads defaults from config/*.yaml and allows overrides saved to config/runtime_settings.yaml
"""
from pathlib import Path
from typing import Any
import os
import time
import yaml
from loguru import logger
import threading

try:
    import fcntl
except ImportError:  # Windows local only
    fcntl = None

_BOOKING_LOCK = threading.RLock()
_RUNTIME_LOCK = threading.RLock()

BASE = Path("config")
RUNTIME_FILE = BASE / "runtime_settings.yaml"
RUNTIME_LOCK_FILE = BASE / "runtime_settings.lock"

# Delay between outbound Telegram notifies (bulk cancel, etc.) seconds
NOTIFY_DELAY_SEC = float(os.getenv("NOTIFY_DELAY_SEC", "0.35"))


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _save_yaml(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)


def _with_file_lock(exclusive: bool = True):
    """Context manager: process-level lock for runtime_settings.yaml."""
    class _LockCtx:
        def __enter__(self):
            RUNTIME_LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
            self._fh = open(RUNTIME_LOCK_FILE, "a+", encoding="utf-8")
            if fcntl is not None:
                flag = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
                # retry a few times if locked
                for _ in range(50):
                    try:
                        fcntl.flock(self._fh.fileno(), flag | fcntl.LOCK_NB)
                        break
                    except BlockingIOError:
                        time.sleep(0.05)
                else:
                    fcntl.flock(self._fh.fileno(), flag)
            return self

        def __exit__(self, *args):
            if fcntl is not None:
                try:
                    fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
                except Exception:
                    pass
            try:
                self._fh.close()
            except Exception:
                pass

    return _LockCtx()


def get_runtime() -> dict:
    with _RUNTIME_LOCK:
        with _with_file_lock(exclusive=False):
            return _load_yaml(RUNTIME_FILE)


def save_runtime(data: dict):
    with _RUNTIME_LOCK:
        with _with_file_lock(exclusive=True):
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


def format_client_line(telegram_id: int, tg_full_name, ref_date: str = "") -> str:
    """Line for group messages: Telegram name + contact + one relevant past visit."""
    tg = tg_full_name or "Клиент"
    contact = get_client_contact_name(telegram_id)
    last = format_last_services_line(telegram_id, ref_date=ref_date or "")
    if contact:
        return f"👤 {tg}\n📱 В контактах: <b>{contact}</b>\n🗂 {last}"
    return f"👤 {tg}\n🗂 {last}"


# ---------- Blocked days (persist) ----------

def _day_reasons(runtime: dict | None = None) -> dict:
    """
    Map DD/MM/YYYY -> 'block' | 'vacation'.
    Migrates legacy blocked_days list (treated as simple block).
    """
    runtime = runtime if runtime is not None else get_runtime()
    reasons = dict(runtime.get("day_reasons", {}) or {})
    legacy = runtime.get("blocked_days", []) or []
    for d in legacy:
        if d not in reasons:
            reasons[d] = "block"
    return reasons


def _save_day_reasons(reasons: dict):
    runtime = get_runtime()
    # keep blocked_days in sync for older code paths
    runtime["day_reasons"] = reasons
    runtime["blocked_days"] = sorted(reasons.keys())
    save_runtime(runtime)


def get_blocked_days() -> set:
    return set(_day_reasons().keys())


def is_blocked(date_str: str) -> bool:
    """date_str in DD/MM/YYYY — any closed day (block or vacation)."""
    return date_str in _day_reasons()


def get_day_close_reason(date_str: str) -> str | None:
    """Return 'vacation', 'block', or None if open."""
    return _day_reasons().get(date_str)


def get_vacation_end_for(date_str: str) -> str | None:
    """
    If date is in a vacation stretch, return the last consecutive vacation day
    (for client message «until X»).
    """
    reasons = _day_reasons()
    if reasons.get(date_str) != "vacation":
        return None
    from datetime import datetime, timedelta
    cur = datetime.strptime(date_str, "%d/%m/%Y").date()
    end = cur
    while True:
        nxt = end + timedelta(days=1)
        key = nxt.strftime("%d/%m/%Y")
        if reasons.get(key) == "vacation":
            end = nxt
        else:
            break
    return end.strftime("%d/%m/%Y")


def block_day(date_str: str, reason: str = "block"):
    reasons = _day_reasons()
    reasons[date_str] = reason if reason in ("block", "vacation") else "block"
    _save_day_reasons(reasons)


def unblock_day(date_str: str):
    reasons = _day_reasons()
    reasons.pop(date_str, None)
    _save_day_reasons(reasons)


def block_range(start_str: str, end_str: str, reason: str = "vacation"):
    from datetime import datetime, timedelta
    start = datetime.strptime(start_str, "%d/%m/%Y").date()
    end = datetime.strptime(end_str, "%d/%m/%Y").date()
    reasons = _day_reasons()
    r = reason if reason in ("block", "vacation") else "vacation"
    cur = start
    while cur <= end:
        reasons[cur.strftime("%d/%m/%Y")] = r
        cur += timedelta(days=1)
    _save_day_reasons(reasons)


def unblock_range(start_str: str, end_str: str) -> int:
    """Remove blocks from start to end inclusive. Returns number of days removed."""
    from datetime import datetime, timedelta
    start = datetime.strptime(start_str, "%d/%m/%Y").date()
    end = datetime.strptime(end_str, "%d/%m/%Y").date()
    reasons = _day_reasons()
    removed = 0
    cur = start
    while cur <= end:
        key = cur.strftime("%d/%m/%Y")
        if key in reasons:
            del reasons[key]
            removed += 1
        cur += timedelta(days=1)
    _save_day_reasons(reasons)
    return removed


def clear_all_blocked() -> int:
    runtime = get_runtime()
    reasons = _day_reasons(runtime)
    count = len(reasons)
    runtime["day_reasons"] = {}
    runtime["blocked_days"] = []
    save_runtime(runtime)
    return count


# ---------- Daily capacity (max requests per day) ----------

def get_max_bookings_per_day() -> int:
    runtime = get_runtime()
    try:
        return max(1, int(runtime.get("max_bookings_per_day", 8)))
    except Exception:
        return 8


def save_max_bookings_per_day(n: int):
    runtime = get_runtime()
    runtime["max_bookings_per_day"] = max(1, int(n))
    save_runtime(runtime)


def count_demand_for_date(date_str: str) -> int:
    """
    How many slots are already taken for this calendar day:
    active confirmed bookings + pending requests for that date.
    """
    n = 0
    for b in get_all_active_bookings():
        if (b.get("date") or "") == date_str:
            n += 1
    runtime = get_runtime()
    pending = runtime.get("pending_bookings", {}) or {}
    for _uid, p in pending.items():
        if isinstance(p, dict) and (p.get("date") or "") == date_str:
            n += 1
    return n


def is_day_full(date_str: str) -> bool:
    return count_demand_for_date(date_str) >= get_max_bookings_per_day()


def client_unavailable_message(date_str: str, lang: str = "ru") -> str:
    """Friendly text when day is closed (vacation vs simple block) or full."""
    reason = get_day_close_reason(date_str)
    if reason == "vacation":
        until = get_vacation_end_for(date_str) or date_str
        if lang == "lv":
            return (
                f"Paldies par interesi! 🙏\n\n"
                f"Diemžēl līdz <b>{until}</b> esmu atpūtā / atvaļinājumā.\n"
                f"Tu vari pierakstīties uz datumu <b>pēc {until}</b> — "
                f"tiklīdz būšu atpakaļ, apskatīšu pieteikumus.\n\n"
                f"Uz drīzu tikšanos!\nTavs labākais bārddzinis ✂️"
            )
        return (
            f"Спасибо за интерес! 🙏\n\n"
            f"К сожалению, до <b>{until}</b> я на отдыхе / в отпуске.\n"
            f"Можно записаться на дату <b>после {until}</b> — "
            f"как вернусь, посмотрю заявки.\n\n"
            f"До скорой встречи!\nВаш лучший барбер ✂️"
        )
    if reason == "block":
        if lang == "lv":
            return (
                f"Šī diena (<b>{date_str}</b>) nav pieejama pierakstam.\n"
                f"Lūdzu, izvēlieties citu dienu."
            )
        return (
            f"Этот день (<b>{date_str}</b>) недоступен для записи.\n"
            f"Пожалуйста, выберите другой день."
        )
    # capacity full (not closed)
    limit = get_max_bookings_per_day()
    if lang == "lv":
        return (
            f"Uz <b>{date_str}</b> jau ir pietiekami daudz pieteikumu "
            f"(limits ~{limit}).\n"
            f"Lūdzu, izvēlieties citu dienu vai rakstiet caur /contact."
        )
    return (
        f"На <b>{date_str}</b> уже достаточно заявок "
        f"(лимит ~{limit}).\n"
        f"Пожалуйста, выберите другой день или напишите через /contact."
    )


# ---------- Pending bookings (for confirm → calendar) ----------

def save_pending_booking(
    user_id: int,
    date_str: str,
    comment: str,
    client_name: str = "",
    kind: str = "book",
    reschedule_id: str = "",
    old_date: str = "",
):
    runtime = get_runtime()
    pending = runtime.get("pending_bookings", {}) or {}
    pending[str(user_id)] = {
        "date": date_str,
        "comment": comment,
        "client_name": client_name,
        "kind": kind or "book",
        "reschedule_id": reschedule_id or "",
        "old_date": old_date or "",
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


def _parse_ddmmyyyy(s: str):
    try:
        parts = (s or "").strip().split("/")
        if len(parts) != 3:
            return None
        d, m, y = int(parts[0]), int(parts[1]), int(parts[2])
        from datetime import date
        return date(y, m, d)
    except Exception:
        return None


def get_all_active_services(user_id: int) -> list:
    """All active history entries, newest first (by date when parseable)."""
    runtime = get_runtime()
    history = runtime.get("service_history", {}) or {}
    entries = history.get(str(user_id), [])
    if not isinstance(entries, list):
        return []
    active = [e for e in entries if e.get("status", "active") != "cancelled"]

    def sort_key(e):
        d = _parse_ddmmyyyy(e.get("date") or "")
        # newest first; undated go last
        return (0, d.toordinal()) if d else (1, 0)

    active_sorted = sorted(active, key=sort_key, reverse=True)
    return active_sorted


def get_last_services(user_id: int, limit: int = 3) -> list:
    """Return last N *active* services, newest first."""
    return get_all_active_services(user_id)[: max(0, limit)]


def filter_services_by_date(
    user_id: int,
    date_from: str = "",
    date_to: str = "",
) -> list:
    """Active services within [date_from, date_to] inclusive (DD/MM/YYYY). Empty bound = open."""
    items = get_all_active_services(user_id)
    d_from = _parse_ddmmyyyy(date_from) if date_from else None
    d_to = _parse_ddmmyyyy(date_to) if date_to else None
    out = []
    for e in items:
        ed = _parse_ddmmyyyy(e.get("date") or "")
        if d_from and (not ed or ed < d_from):
            continue
        if d_to and (not ed or ed > d_to):
            continue
        out.append(e)
    return out


def get_history_page(
    user_id: int,
    page: int = 0,
    page_size: int = 5,
    date_from: str = "",
    date_to: str = "",
) -> dict:
    """Paginated history. Returns items, page, total_pages, total."""
    if date_from or date_to:
        items = filter_services_by_date(user_id, date_from, date_to)
    else:
        items = get_all_active_services(user_id)
    total = len(items)
    page_size = max(1, page_size)
    total_pages = max(1, (total + page_size - 1) // page_size) if total else 1
    page = max(0, min(page, total_pages - 1))
    chunk = items[page * page_size : (page + 1) * page_size]
    return {
        "items": chunk,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "total": total,
    }


def get_relevant_past_service(user_id: int, ref_date: str = "") -> dict | None:
    """
    One visit for barber context on a booking request:
    - ref_date set → closest visit on or before that date
    - else → most recent active visit
    """
    all_active = get_all_active_services(user_id)
    if not all_active:
        return None
    ref = _parse_ddmmyyyy(ref_date) if ref_date else None
    if not ref:
        return all_active[0]
    best = None
    best_delta = None
    for e in all_active:
        ed = _parse_ddmmyyyy(e.get("date") or "")
        if not ed or ed > ref:
            continue
        delta = (ref - ed).days
        if best_delta is None or delta < best_delta:
            best_delta = delta
            best = e
    return best or all_active[0]


def format_last_services_line(user_id: int, limit: int = 1, ref_date: str = "") -> str:
    """Single relevant past visit for group booking cards."""
    e = get_relevant_past_service(user_id, ref_date=ref_date)
    if not e:
        return "Last time used services: —"
    svc = e.get("service", "—")
    dt = e.get("date", "")
    if dt and ref_date:
        ref = _parse_ddmmyyyy(ref_date)
        ed = _parse_ddmmyyyy(dt)
        if ref and ed:
            days = (ref - ed).days
            if days == 0:
                ago = "в тот же день"
            elif days == 1:
                ago = "1 день назад"
            elif days < 30:
                ago = f"{days} дн. назад"
            else:
                ago = f"~{days // 7} нед. назад"
            return f"Last time used services: {svc} ({dt}, {ago})"
        return f"Last time used services: {svc} ({dt})"
    if dt:
        return f"Last time used services: {svc} ({dt})"
    return f"Last time used services: {svc}"


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


def cancel_booking(booking_id: str, by: str = "barber") -> dict:
    """
    Idempotent cancel under lock.
    Returns dict:
      ok: bool
      reason: cancelled | already_cancelled | not_found
      booking: dict | None
      cancelled_by: str | None  (who cancelled first, if already done)
    """
    with _BOOKING_LOCK:
        existing = get_booking(booking_id)
        if not existing:
            return {"ok": False, "reason": "not_found", "booking": None, "cancelled_by": None}
        status = existing.get("status", "")
        if status != "confirmed":
            who = None
            if status.startswith("cancelled_by_"):
                who = status.replace("cancelled_by_", "", 1)
            return {
                "ok": False,
                "reason": "already_cancelled",
                "booking": existing,
                "cancelled_by": who or status,
            }
        b = update_booking(booking_id, status=f"cancelled_by_{by}")
        cancel_service_history(int(b["user_id"]), booking_id=booking_id, date_str=b.get("date", ""))
        return {"ok": True, "reason": "cancelled", "booking": b, "cancelled_by": by}


def reschedule_booking(
    booking_id: str,
    new_date: str,
    new_comment: str,
) -> dict:
    """
    Update date/comment on a confirmed booking; reset reminder flags.
    Returns same shape as cancel_booking for consistency.
    """
    with _BOOKING_LOCK:
        existing = get_booking(booking_id)
        if not existing:
            return {"ok": False, "reason": "not_found", "booking": None}
        if existing.get("status") != "confirmed":
            return {
                "ok": False,
                "reason": "not_active",
                "booking": existing,
            }
        b = update_booking(
            booking_id,
            date=new_date,
            comment=new_comment,
            reminder_24h_sent=False,
            reminder_morning_sent=False,
            client_confirmed=False,
            client_thinking=False,
            # keep calendar_event_id; caller may recreate event
        )
        # Update history entry text for this booking_id
        runtime = get_runtime()
        history = runtime.get("service_history", {}) or {}
        key = str(b.get("user_id"))
        entries = history.get(key, [])
        if isinstance(entries, list):
            for e in entries:
                if e.get("booking_id") == booking_id and e.get("status", "active") != "cancelled":
                    e["date"] = new_date
                    e["service"] = (new_comment or "").strip() or e.get("service", "—")
            history[key] = entries
            runtime["service_history"] = history
            save_runtime(runtime)
        return {"ok": True, "reason": "rescheduled", "booking": b}


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


def get_all_active_bookings() -> list:
    """All confirmed (not cancelled) bookings, newest last."""
    return [b for b in get_confirmed_bookings() if b.get("status") == "confirmed"]


def find_active_bookings(query: str) -> list:
    """Search active bookings by contact name, telegram name, comment, date, or id."""
    q = (query or "").strip().lower()
    if not q:
        return get_all_active_bookings()
    results = []
    for b in get_all_active_bookings():
        uid = int(b.get("user_id", 0))
        contact = (get_client_contact_name(uid) or "").lower()
        name = (b.get("client_name") or "").lower()
        comment = (b.get("comment") or "").lower()
        date = (b.get("date") or "").lower()
        bid = str(b.get("id", "")).lower()
        hay = f"{contact} {name} {comment} {date} {bid} {uid}"
        if q in hay:
            results.append(b)
    return results


# ---------- Simple analytics ----------

def track_event(event: str, user_id: int | None = None):
    """Increment counters for funnel stats."""
    from datetime import datetime
    with _BOOKING_LOCK:
        runtime = get_runtime()
        stats = runtime.get("stats", {}) or {}
        stats["total_" + event] = int(stats.get("total_" + event, 0)) + 1
        users_key = "users_" + event
        users = set(stats.get(users_key, []) or [])
        if user_id is not None:
            users.add(str(user_id))
        # keep list compact
        stats[users_key] = list(users)[-5000:]
        day = datetime.now().strftime("%Y-%m-%d")
        daily = stats.get("daily", {}) or {}
        day_bucket = daily.get(day, {}) or {}
        day_bucket[event] = int(day_bucket.get(event, 0)) + 1
        daily[day] = day_bucket
        # keep last 60 days
        for k in sorted(daily.keys())[:-60]:
            daily.pop(k, None)
        stats["daily"] = daily
        runtime["stats"] = stats
        save_runtime(runtime)


def get_stats_summary() -> str:
    runtime = get_runtime()
    stats = runtime.get("stats", {}) or {}
    def n(event):
        return int(stats.get("total_" + event, 0))
    def u(event):
        return len(stats.get("users_" + event, []) or [])
    lines = [
        "📊 <b>Статистика бота</b>",
        "",
        f"▶️ /start: <b>{n('start')}</b> (уник. {u('start')})",
        f"📝 Заявки: <b>{n('book_request')}</b> (уник. {u('book_request')})",
        f"✅ Подтверждено: <b>{n('booking_confirmed')}</b>",
        f"📅 Запросы переноса: <b>{n('reschedule_request')}</b>",
        f"✅ Переносы приняты: <b>{n('reschedule_confirmed')}</b>",
        f"❌ Отмены клиент: <b>{n('cancel_client')}</b>",
        f"❌ Отмены барбер: <b>{n('cancel_barber')}</b>",
        "",
        f"Активных записей сейчас: <b>{len(get_all_active_bookings())}</b>",
    ]
    daily = stats.get("daily", {}) or {}
    if daily:
        last_days = sorted(daily.keys())[-7:]
        lines.append("")
        lines.append("<b>Последние 7 дней</b> (start / book / confirm):")
        for d in last_days:
            b = daily[d]
            lines.append(
                f"• {d}: {b.get('start', 0)} / {b.get('book_request', 0)} / {b.get('booking_confirmed', 0)}"
            )
    return "\n".join(lines)
