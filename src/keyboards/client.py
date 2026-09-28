from aiogram.types import ReplyKeyboardMarkup, InlineKeyboardMarkup
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder


def main_menu_kb(lang: str = "ru") -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    if lang == "ru":
        builder.button(text="📅 Записаться")
        builder.button(text="📋 История записей")
        builder.button(text="💰 Цены")
        builder.button(text="📞 Связаться")
        builder.button(text="❌ Отменить запись")
        builder.button(text="📅 Перенести запись")
        builder.button(text="🌐 Language / Valoda")
    else:
        builder.button(text="📅 Pierakstīties")
        builder.button(text="📋 Pierakstu vēsture")
        builder.button(text="💰 Cenas")
        builder.button(text="📞 Sazināties")
        builder.button(text="❌ Atcelt pierakstu")
        builder.button(text="📅 Pārcelt pierakstu")
        builder.button(text="🌐 Language / Valoda")
    builder.adjust(2, 2, 2, 1)
    return builder.as_markup(resize_keyboard=True)


def language_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🇷🇺 Русский", callback_data="lang:ru")
    builder.button(text="🇱🇻 Latviešu", callback_data="lang:lv")
    builder.adjust(2)
    return builder.as_markup()


def day_selection_kb(lang: str = "ru") -> InlineKeyboardMarkup:
    """Hide only blocked/vacation days. Capacity limit removed — calendar slots decide."""
    from src.services import settings_store as store
    from datetime import datetime, timedelta

    builder = InlineKeyboardBuilder()
    today = datetime.now().date()
    options = [
        ("today", 0, "Сегодня" if lang == "ru" else "Šodien"),
        ("tomorrow", 1, "Завтра" if lang == "ru" else "Rīt"),
        ("day_after", 2, "Послезавтра" if lang == "ru" else "Parīt"),
    ]
    for key, offset, label in options:
        d = (today + timedelta(days=offset)).strftime("%d/%m/%Y")
        if store.is_blocked(d):
            continue
        builder.button(text=label, callback_data=f"day:{key}")
    other = "Другая дата" if lang == "ru" else "Cita datums"
    builder.button(text=other, callback_data="day:other")
    builder.adjust(1)
    return builder.as_markup()


_SLOT_KB_CACHE: dict = {}
_SLOT_KB_TTL = 45.0


def slot_selection_kb(slots: list[str], lang: str = "ru") -> InlineKeyboardMarkup:
    """Available time slots; short in-memory cache of markup for same slot list."""
    import time
    key = (lang, tuple(slots))
    hit = _SLOT_KB_CACHE.get(key)
    if hit and time.time() - hit[0] < _SLOT_KB_TTL:
        return hit[1]
    builder = InlineKeyboardBuilder()
    for s in slots:
        builder.button(text=s, callback_data=f"slot:{s}")
    back = "« Другой день" if lang == "ru" else "« Cita diena"
    builder.button(text=back, callback_data="slot:back")
    # 3 per row for times, back full width
    n = len(slots)
    row_sizes = [3] * (n // 3)
    if n % 3:
        row_sizes.append(n % 3)
    row_sizes.append(1)
    builder.adjust(*row_sizes)
    markup = builder.as_markup()
    _SLOT_KB_CACHE[key] = (time.time(), markup)
    # bound cache size
    if len(_SLOT_KB_CACHE) > 40:
        oldest = sorted(_SLOT_KB_CACHE.items(), key=lambda x: x[1][0])[:10]
        for k, _ in oldest:
            _SLOT_KB_CACHE.pop(k, None)
    return markup


def service_selection_kb(lang: str = "ru") -> InlineKeyboardMarkup:
    from src.services import settings_store as store
    builder = InlineKeyboardBuilder()
    for s in store.get_services():
        if not s.get("is_active", True):
            continue
        name = s.get("name_ru") if lang == "ru" else s.get("name_lv")
        price = s.get("price", "?")
        sid = s.get("id") or ""
        if not sid:
            continue
        builder.button(
            text=f"{name} — {price}€",
            callback_data=f"svc:{sid}",
        )
    skip = "Пропустить / свой текст" if lang == "ru" else "Izlaist / savs teksts"
    builder.button(text=skip, callback_data="svc:skip")
    builder.adjust(1)
    return builder.as_markup()
