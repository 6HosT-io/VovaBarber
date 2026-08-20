import os
from datetime import datetime, timedelta

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from loguru import logger

router = Router()

# Blocked days are persisted via settings_store


class SettingsStates(StatesGroup):
    edit_location = State()
    edit_prices = State()
    edit_hours = State()
    edit_welcome_ru = State()
    edit_welcome_lv = State()
    edit_reminder = State()


def get_admin_ids() -> list[int]:
    raw = os.getenv("ADMIN_IDS", "")
    ids = []
    for x in raw.split(","):
        x = x.strip()
        if x.isdigit():
            ids.append(int(x))
    return ids


def get_admin_group() -> str | None:
    return os.getenv("ADMIN_GROUP_ID") or None


def is_admin(user_id: int) -> bool:
    return user_id in get_admin_ids()


def parse_ddmmyyyy(text: str):
    """Parse DD/MM/YYYY or DD.MM.YYYY. Returns date or None."""
    text = (text or "").strip().replace(".", "/").replace("-", "/")
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def to_display(d) -> str:
    return d.strftime("%d/%m/%Y")


DATE_FMT_HELP = (
    "Формат даты: <b>ДД/ММ/ГГГГ</b>\n"
    "Примеры: <code>25/08/2026</code>, <code>01/09/2026</code>"
)

MAX_RANGE_DAYS = 90  # safety limit for vacation / unvacation


def validate_single_date(raw: str):
    """Returns (date|None, error_message|None)"""
    if not raw or not raw.strip():
        return None, f"Не указана дата.\n\n{DATE_FMT_HELP}"
    d = parse_ddmmyyyy(raw)
    if not d:
        return None, (
            f"Не понял дату: <code>{raw}</code>\n\n"
            f"{DATE_FMT_HELP}\n\n"
            f"Пример команды:\n<code>/block 25/08/2026</code>"
        )
    return d, None


def validate_date_range(raw_start: str, raw_end: str):
    """Returns (start, end, error_message|None)"""
    start, err = validate_single_date(raw_start)
    if err:
        return None, None, err.replace("/block", "/vacation")
    end, err = validate_single_date(raw_end)
    if err:
        return None, None, err.replace("/block", "/vacation")
    if end < start:
        return None, None, (
            "Дата окончания раньше начала.\n\n"
            f"Начало: <b>{to_display(start)}</b>\n"
            f"Конец: <b>{to_display(end)}</b>\n\n"
            "Нужно: сначала ранняя дата, потом поздняя.\n"
            "Пример: <code>/vacation 01/09/2026 14/09/2026</code>"
        )
    span = (end - start).days + 1
    if span > MAX_RANGE_DAYS:
        return None, None, (
            f"Слишком большой диапазон: <b>{span}</b> дн. "
            f"(лимит {MAX_RANGE_DAYS}).\n\n"
            "Разбейте на несколько команд или проверьте даты."
        )
    return start, end, None


def settings_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Цены и услуги", callback_data="set:prices")],
        [InlineKeyboardButton(text="🕐 Рабочие часы", callback_data="set:hours")],
        [InlineKeyboardButton(text="📍 Адрес", callback_data="set:location")],
        [InlineKeyboardButton(text="👋 Текст приветствия", callback_data="set:welcome")],
        [InlineKeyboardButton(text="🔔 Тексты напоминаний", callback_data="set:reminders")],
        [InlineKeyboardButton(text="🔒 Заблокированные дни", callback_data="set:blocked")],
        [InlineKeyboardButton(text="📋 Показать всё", callback_data="set:show")],
    ])


@router.message(Command("admin", "panel"))
async def cmd_admin(message: Message):
    logger.info(f"/admin from {message.from_user.id}, allowed={get_admin_ids()}")
    if not is_admin(message.from_user.id):
        return

    text = (
        "🔧 <b>Admin panel</b>\n\n"
        "Команды:\n"
        "/admin /panel — это меню\n"
        "/settings — настройки\n"
        "/test_group — проверить группу\n"
        "/block ДД/ММ/ГГГГ — один день\n"
        "/unblock ДД/ММ/ГГГГ — один день\n"
        "/vacation ДД/ММ/ГГГГ ДД/ММ/ГГГГ — блок диапазона\n"
        "/unvacation ДД/ММ/ГГГГ ДД/ММ/ГГГГ — снять блок с диапазона\n"
        "/unblock_all — снять все блокировки\n"
        "/bookings — активные записи\n"
        "/bookings имя — поиск по клиенту\n"
        "/cancel_id ID — отмена по ID\n\n"
        f"Группа: <code>{get_admin_group() or '—'}</code>\n"
        f"Твой ID: <code>{message.from_user.id}</code>"
    )
    await message.answer(text)


@router.message(Command("settings"))
async def cmd_settings(message: Message):
    logger.info(f"/settings from {message.from_user.id}")
    if not is_admin(message.from_user.id):
        return
    await message.answer(
        "⚙️ <b>Настройки бота</b>\n\n"
        "Формат даты: <b>ДД/ММ/ГГГГ</b> (фиксирован)\n"
        "Выберите, что изменить:",
        reply_markup=settings_kb(),
    )


@router.message(Command("test_group", "test-group", "testgroup"))
async def cmd_test_group(message: Message):
    logger.info(f"/test_group from {message.from_user.id}")
    if not is_admin(message.from_user.id):
        return

    group = get_admin_group()
    if not group:
        await message.answer("ADMIN_GROUP_ID не задан в .env")
        return

    from src.bot import bot
    try:
        chat_id = int(group)
        await bot.send_message(
            chat_id=chat_id,
            text=(
                f"✅ Тест уведомления\n"
                f"От: {message.from_user.full_name} (id {message.from_user.id})\n"
                f"Группа получает сообщения от бота."
            ),
        )
        await message.answer("Сообщение отправлено в группу. Проверь группу.")
        logger.info(f"Test OK → {chat_id}")
    except Exception as e:
        await message.answer(
            f"❌ Не удалось отправить в группу.\n"
            f"Ошибка: <code>{e}</code>\n\n"
            f"ID группы: <code>{group}</code>\n"
            "Проверь: бот админ, право Post Messages, ID с -100"
        )
        logger.error(f"test_group failed: {e}")


# ---------- Settings callbacks (need settings_store) ----------

@router.callback_query(F.data == "set:show")
async def settings_show(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return
    try:
        from src.services import settings_store as store
        prices = store.format_services_text("ru")
        hours = store.format_hours_text()
        location = store.get_location()
    except Exception as e:
        await callback.message.edit_text(f"Ошибка загрузки настроек: {e}")
        await callback.answer()
        return
    from src.services import settings_store as store
    blocked_list = sorted(store.get_blocked_days())
    blocked = ", ".join(blocked_list) if blocked_list else "нет"
    text = (
        f"📋 <b>Текущие настройки</b>\n\n"
        f"<b>Цены:</b>\n{prices}\n\n"
        f"<b>Часы:</b>\n{hours}\n\n"
        f"<b>Адрес:</b>\n{location}\n\n"
        f"<b>Заблокированные дни:</b>\n{blocked}\n\n"
        f"<b>Формат даты:</b> ДД/ММ/ГГГГ"
    )
    await callback.message.edit_text(text, reply_markup=settings_kb())
    await callback.answer()


@router.callback_query(F.data == "set:location")
async def settings_location(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return
    from src.services import settings_store as store
    current = store.get_location()
    await state.set_state(SettingsStates.edit_location)
    await callback.message.edit_text(
        f"📍 Текущий адрес:\n<code>{current}</code>\n\n"
        "Пришлите новый адрес одним сообщением.\n/cancel — отмена"
    )
    await callback.answer()


@router.message(SettingsStates.edit_location)
async def save_location(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if message.text and message.text.startswith("/cancel"):
        await state.clear()
        await message.answer("Отменено.")
        return
    from src.services import settings_store as store
    store.save_location(message.text.strip())
    await state.clear()
    await message.answer(f"✅ Адрес сохранён:\n{message.text.strip()}")


@router.callback_query(F.data == "set:prices")
async def settings_prices(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return
    from src.services import settings_store as store
    current = store.format_services_text("ru")
    await state.set_state(SettingsStates.edit_prices)
    await callback.message.edit_text(
        f"💰 Текущие цены:\n{current}\n\n"
        "Формат каждой строки:\n"
        "<code>название | цена | минуты</code>\n\n"
        "Пример:\n"
        "<code>Мужская стрижка | 20 | 30\n"
        "Полный пакет | 25 | 45</code>\n\n"
        "/cancel — отмена"
    )
    await callback.answer()


@router.message(SettingsStates.edit_prices)
async def save_prices(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if message.text and message.text.startswith("/cancel"):
        await state.clear()
        await message.answer("Отменено.")
        return
    from src.services import settings_store as store
    lines = [ln.strip() for ln in (message.text or "").splitlines() if ln.strip()]
    services = []
    for i, line in enumerate(lines):
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 2:
            await message.answer(f"Не разобрал: {line}")
            return
        name = parts[0]
        try:
            price = float(parts[1].replace(",", ".").replace("€", "").strip())
        except ValueError:
            await message.answer(f"Неверная цена: {line}")
            return
        duration = 30
        if len(parts) >= 3:
            try:
                duration = int(parts[2].strip())
            except ValueError:
                pass
        services.append({
            "id": f"svc_{i}",
            "name_ru": name,
            "name_lv": name,
            "price": price,
            "duration_min": duration,
            "is_active": True,
        })
    if not services:
        await message.answer("Пустой список.")
        return
    store.save_services(services)
    await state.clear()
    await message.answer("✅ Цены обновлены:\n" + store.format_services_text("ru"))


@router.callback_query(F.data == "set:hours")
async def settings_hours(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return
    from src.services import settings_store as store
    current = store.format_hours_text()
    await state.set_state(SettingsStates.edit_hours)
    await callback.message.edit_text(
        f"🕐 Текущие часы:\n{current}\n\n"
        "Формат:\n"
        "<code>weekdays: 10:00-12:00, 14:00-22:00\n"
        "saturday: 10:00-22:00\n"
        "sunday: closed</code>\n\n"
        "/cancel — отмена"
    )
    await callback.answer()


@router.message(SettingsStates.edit_hours)
async def save_hours(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if message.text and message.text.startswith("/cancel"):
        await state.clear()
        await message.answer("Отменено.")
        return
    from src.services import settings_store as store
    hours = {"weekdays": [], "saturday": [], "sunday": []}
    for raw in (message.text or "").splitlines():
        line = raw.strip().lower()
        if not line or ":" not in line:
            continue
        key, val = line.split(":", 1)
        key, val = key.strip(), val.strip()
        if "closed" in val or "выход" in val or val == "":
            slots = []
        else:
            slots = []
            for part in val.split(","):
                part = part.strip().replace("–", "-").replace("—", "-")
                if "-" in part:
                    a, b = part.split("-", 1)
                    slots.append({"start": a.strip(), "end": b.strip()})
        if key.startswith("week") or key in ("пн", "будни"):
            hours["weekdays"] = slots
        elif key.startswith("sat") or key == "сб":
            hours["saturday"] = slots
        elif key.startswith("sun") or key == "вс":
            hours["sunday"] = slots
    store.save_working_hours(hours)
    await state.clear()
    await message.answer("✅ Часы сохранены:\n" + store.format_hours_text())


@router.callback_query(F.data == "set:welcome")
async def settings_welcome(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return
    from src.services import settings_store as store
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="set:welcome_ru")],
        [InlineKeyboardButton(text="🇱🇻 Latviešu", callback_data="set:welcome_lv")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="set:back")],
    ])
    await callback.message.edit_text(
        f"👋 Приветствия\n\n"
        f"<b>RU:</b>\n{store.get_welcome_text('ru')}\n\n"
        f"<b>LV:</b>\n{store.get_welcome_text('lv')}",
        reply_markup=kb,
    )
    await callback.answer()


@router.callback_query(F.data == "set:welcome_ru")
async def settings_welcome_ru(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(SettingsStates.edit_welcome_ru)
    await callback.message.edit_text("Пришлите новый текст (RU).\n/cancel — отмена")
    await callback.answer()


@router.callback_query(F.data == "set:welcome_lv")
async def settings_welcome_lv(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(SettingsStates.edit_welcome_lv)
    await callback.message.edit_text("Atsūtiet tekstu (LV).\n/cancel — atcelt")
    await callback.answer()


@router.message(SettingsStates.edit_welcome_ru)
async def save_welcome_ru(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if message.text and message.text.startswith("/cancel"):
        await state.clear()
        await message.answer("Отменено.")
        return
    from src.services import settings_store as store
    store.save_welcome_text("ru", message.text.strip())
    await state.clear()
    await message.answer("✅ Приветствие (RU) сохранено.")


@router.message(SettingsStates.edit_welcome_lv)
async def save_welcome_lv(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if message.text and message.text.startswith("/cancel"):
        await state.clear()
        await message.answer("Atcelts.")
        return
    from src.services import settings_store as store
    store.save_welcome_text("lv", message.text.strip())
    await state.clear()
    await message.answer("✅ Sveiciens (LV) saglabāts.")


@router.callback_query(F.data == "set:reminders")
async def settings_reminders(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    from src.services import settings_store as store
    t = store.get_reminder_texts()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="24ч RU", callback_data="set:rem:reminder_24h_ru")],
        [InlineKeyboardButton(text="24h LV", callback_data="set:rem:reminder_24h_lv")],
        [InlineKeyboardButton(text="Утро RU", callback_data="set:rem:reminder_morning_ru")],
        [InlineKeyboardButton(text="Rīts LV", callback_data="set:rem:reminder_morning_lv")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="set:back")],
    ])
    await callback.message.edit_text(
        f"🔔 Напоминания\n\n"
        f"24ч RU: {t['reminder_24h_ru']}\n\n"
        f"24h LV: {t['reminder_24h_lv']}\n\n"
        f"Утро RU: {t['reminder_morning_ru']}\n\n"
        f"Rīts LV: {t['reminder_morning_lv']}",
        reply_markup=kb,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("set:rem:"))
async def settings_rem_pick(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    key = callback.data.split(":", 2)[2]
    await state.set_state(SettingsStates.edit_reminder)
    await state.update_data(reminder_key=key)
    await callback.message.edit_text(f"Новый текст для <code>{key}</code>\n/cancel — отмена")
    await callback.answer()


@router.message(SettingsStates.edit_reminder)
async def save_reminder(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if message.text and message.text.startswith("/cancel"):
        await state.clear()
        await message.answer("Отменено.")
        return
    from src.services import settings_store as store
    data = await state.get_data()
    key = data.get("reminder_key")
    if key:
        store.save_reminder_text(key, message.text.strip())
    await state.clear()
    await message.answer("✅ Текст сохранён.")


@router.callback_query(F.data == "set:blocked")
async def settings_blocked(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    from src.services import settings_store as store
    blocked_list = sorted(store.get_blocked_days())
    blocked = ", ".join(blocked_list) if blocked_list else "нет"
    await callback.message.edit_text(
        f"🔒 Заблокированные дни:\n{blocked}\n\n"
        "/block ДД/ММ/ГГГГ\n"
        "/unblock ДД/ММ/ГГГГ\n"
        "/vacation СТАРТ КОНЕЦ\n"
        "/unvacation СТАРТ КОНЕЦ — снять часть отпуска\n"
        "/unblock_all — очистить все",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="set:back")]
        ]),
    )
    await callback.answer()


@router.callback_query(F.data == "set:back")
async def settings_back(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "⚙️ <b>Настройки</b>\nФормат даты: ДД/ММ/ГГГГ\nВыберите раздел:",
        reply_markup=settings_kb(),
    )
    await callback.answer()


@router.message(Command("block"))
async def cmd_block(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = (message.text or "").split()
    if len(parts) < 2:
        await message.answer(
            "🔒 Блок одного дня\n\n"
            "Синтаксис:\n<code>/block ДД/ММ/ГГГГ</code>\n\n"
            "Пример:\n<code>/block 25/08/2026</code>"
        )
        return
    d, err = validate_single_date(parts[1])
    if err:
        await message.answer(err)
        return
    key = to_display(d)
    from src.services import settings_store as store
    store.block_day(key)
    await message.answer(f"🔒 День <b>{key}</b> заблокирован.")


@router.message(Command("unblock"))
async def cmd_unblock(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = (message.text or "").split()
    if len(parts) < 2:
        await message.answer(
            "🔓 Снять блок с одного дня\n\n"
            "Синтаксис:\n<code>/unblock ДД/ММ/ГГГГ</code>\n\n"
            "Пример:\n<code>/unblock 25/08/2026</code>"
        )
        return
    d, err = validate_single_date(parts[1])
    if err:
        await message.answer(err.replace("/block", "/unblock"))
        return
    key = to_display(d)
    from src.services import settings_store as store
    store.unblock_day(key)
    await message.answer(f"🔓 День <b>{key}</b> разблокирован.")


@router.message(Command("vacation"))
async def cmd_vacation(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = (message.text or "").split()
    if len(parts) < 3:
        await message.answer(
            "🏖 Блок диапазона (отпуск)\n\n"
            "Синтаксис:\n"
            "<code>/vacation ДД/ММ/ГГГГ ДД/ММ/ГГГГ</code>\n\n"
            "Пример (2 недели):\n"
            "<code>/vacation 01/09/2026 14/09/2026</code>\n\n"
            f"{DATE_FMT_HELP}\n"
            f"Лимит диапазона: {MAX_RANGE_DAYS} дней."
        )
        return
    start, end, err = validate_date_range(parts[1], parts[2])
    if err:
        await message.answer(err)
        return
    from src.services import settings_store as store
    store.block_range(to_display(start), to_display(end))
    count = (end - start).days + 1
    await message.answer(
        f"🏖 Заблокировано <b>{count}</b> дн.\n"
        f"{to_display(start)} → {to_display(end)}"
    )


@router.message(Command("unvacation", "unblock_range"))
async def cmd_unvacation(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = (message.text or "").split()
    if len(parts) < 3:
        await message.answer(
            "🔓 Снять блок с части отпуска\n\n"
            "Синтаксис:\n"
            "<code>/unvacation ДД/ММ/ГГГГ ДД/ММ/ГГГГ</code>\n\n"
            "Пример: отпуск был 01/09–14/09, открыть вторую неделю:\n"
            "<code>/unvacation 08/09/2026 14/09/2026</code>\n\n"
            f"{DATE_FMT_HELP}"
        )
        return
    start, end, err = validate_date_range(parts[1], parts[2])
    if err:
        await message.answer(err)
        return
    from src.services import settings_store as store
    removed = store.unblock_range(to_display(start), to_display(end))
    await message.answer(
        f"🔓 Снят блок с <b>{removed}</b> дн.\n"
        f"{to_display(start)} → {to_display(end)}"
    )


@router.message(Command("unblock_all", "clear_blocks"))
async def cmd_unblock_all(message: Message):
    if not is_admin(message.from_user.id):
        return
    from src.services import settings_store as store
    count = store.clear_all_blocked()
    await message.answer(
        f"🔓 Сняты все блокировки (<b>{count}</b> дн.).\n\n"
        "Если нужно снова закрыть дни — /vacation или /block."
    )



PAGE_SIZE = 5


def _bookings_nav_kb(page: int, total_pages: int, query: str = "") -> InlineKeyboardMarkup:
    # query truncated for callback limit
    q = (query or "")[:30]
    rows = []
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(
            text="◀️",
            callback_data=f"bk:p:{page - 1}:{q}",
        ))
    nav.append(InlineKeyboardButton(
        text=f"{page + 1}/{total_pages}",
        callback_data="bk:noop",
    ))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(
            text="▶️",
            callback_data=f"bk:p:{page + 1}:{q}",
        ))
    if nav:
        rows.append(nav)
    rows.append([
        InlineKeyboardButton(
            text="❌ Отменить все на странице",
            callback_data=f"bk:bulkpage:{page}:{q}",
        )
    ])
    if q:
        rows.append([
            InlineKeyboardButton(
                text="❌ Отменить все найденные",
                callback_data=f"bk:bulkall:{q}",
            )
        ])
    else:
        rows.append([
            InlineKeyboardButton(
                text="❌ Отменить ВСЕ активные",
                callback_data="bk:bulkall:",
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _send_bookings_page(target, page: int = 0, query: str = ""):
    """target: Message or CallbackQuery.message"""
    from src.services import settings_store as store

    items = store.find_active_bookings(query) if query else store.get_all_active_bookings()
    items = list(reversed(items))
    total = len(items)
    if total == 0:
        text = (
            "Активных записей нет." if not query
            else f"Ничего не найдено по «{query}».\n"
            "Поиск: имя, контакты, дата, комментарий."
        )
        if hasattr(target, "edit_text"):
            try:
                await target.edit_text(text)
            except Exception:
                await target.answer(text)
        else:
            await target.answer(text)
        return

    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    chunk = items[page * PAGE_SIZE : (page + 1) * PAGE_SIZE]

    header = (
        f"📋 Активные записи: <b>{total}</b>"
        + (f" | поиск: <code>{query}</code>" if query else "")
        + f"\nСтраница <b>{page + 1}/{total_pages}</b>"
    )
    nav = _bookings_nav_kb(page, total_pages, query)

    # Prefer editing the header message when paginating
    if hasattr(target, "edit_text") and getattr(target, "text", None) and target.text.startswith("📋"):
        await target.edit_text(header, reply_markup=nav)
    else:
        await target.answer(header, reply_markup=nav)

    for b in chunk:
        uid = int(b.get("user_id", 0))
        contact = store.get_client_contact_name(uid)
        name = b.get("client_name") or "Клиент"
        line = f"👤 {name}"
        if contact:
            line += f"\n📱 В контактах: <b>{contact}</b>"
        line += (
            f"\n📅 {b.get('date', '—')}"
            f"\n💬 {b.get('comment', '—')}"
            f"\nID: <code>{b.get('id')}</code>"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="❌ Отменить эту запись",
                callback_data=f"adm:cancel:{b.get('id')}",
            )],
            [InlineKeyboardButton(
                text="💬 Написать клиенту",
                url=f"tg://user?id={uid}",
            )],
        ])
        # always send cards as new messages (hard to edit many)
        chat = target.chat if hasattr(target, "chat") else target
        bot = target.bot if hasattr(target, "bot") else None
        if bot:
            await bot.send_message(chat.id, line, reply_markup=kb)
        else:
            await target.answer(line, reply_markup=kb)


@router.message(Command("bookings", "active"))
async def cmd_bookings(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = (message.text or "").split(maxsplit=1)
    query = parts[1].strip() if len(parts) > 1 else ""
    await _send_bookings_page(message, page=0, query=query)


@router.callback_query(F.data.startswith("bk:p:"))
async def bookings_page(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return
    parts = callback.data.split(":", 3)
    # bk:p:PAGE:query
    page = int(parts[2]) if len(parts) > 2 else 0
    query = parts[3] if len(parts) > 3 else ""
    await _send_bookings_page(callback.message, page=page, query=query)
    await callback.answer()


@router.callback_query(F.data == "bk:noop")
async def bookings_noop(callback: CallbackQuery):
    await callback.answer()


@router.callback_query(F.data.startswith("bk:bulkpage:"))
async def bookings_bulk_page_ask(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return
    parts = callback.data.split(":", 3)
    page = parts[2] if len(parts) > 2 else "0"
    query = parts[3] if len(parts) > 3 else ""
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Да, отменить страницу", callback_data=f"bk:dobulkpage:{page}:{query}"),
            InlineKeyboardButton(text="Нет", callback_data="bk:noop"),
        ]
    ])
    await callback.message.answer(
        "Точно отменить <b>все записи на этой странице</b>?",
        reply_markup=kb,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("bk:bulkall"))
async def bookings_bulk_all_ask(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return
    # bk:bulkall: or bk:bulkall:query
    query = callback.data.split(":", 2)[2] if callback.data.count(":") >= 2 else ""
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="Да, отменить все",
                callback_data=f"bk:dobulkall:{query}",
            ),
            InlineKeyboardButton(text="Нет", callback_data="bk:noop"),
        ]
    ])
    scope = f"по поиску «{query}»" if query else "все активные"
    await callback.message.answer(
        f"Точно отменить <b>{scope}</b> записи?",
        reply_markup=kb,
    )
    await callback.answer()


async def _bulk_cancel(bot: Bot, bookings: list) -> int:
    from src.services import settings_store as store
    from src.services import calendar as gcal
    n = 0
    for b in bookings:
        if b.get("status") != "confirmed":
            continue
        store.cancel_booking(b["id"], by="barber")
        try:
            eid = b.get("calendar_event_id")
            if eid:
                gcal.delete_event(eid)
        except Exception:
            pass
        try:
            await bot.send_message(
                int(b["user_id"]),
                f"❌ Запись на <b>{b.get('date')}</b> отменена барбером.\n"
                f"Можно выбрать другое время через /book.",
            )
        except Exception as e:
            logger.error(f"bulk notify: {e}")
        n += 1
    return n


@router.callback_query(F.data.startswith("bk:dobulkpage:"))
async def bookings_do_bulk_page(callback: CallbackQuery, bot: Bot):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return
    from src.services import settings_store as store
    parts = callback.data.split(":", 3)
    page = int(parts[2]) if len(parts) > 2 else 0
    query = parts[3] if len(parts) > 3 else ""
    items = store.find_active_bookings(query) if query else store.get_all_active_bookings()
    items = list(reversed(items))
    chunk = items[page * PAGE_SIZE : (page + 1) * PAGE_SIZE]
    n = await _bulk_cancel(bot, chunk)
    await callback.message.answer(f"✅ Отменено на странице: <b>{n}</b>")
    await callback.answer()


@router.callback_query(F.data.startswith("bk:dobulkall:"))
async def bookings_do_bulk_all(callback: CallbackQuery, bot: Bot):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return
    from src.services import settings_store as store
    query = callback.data.split(":", 2)[2] if callback.data.count(":") >= 2 else ""
    items = store.find_active_bookings(query) if query else store.get_all_active_bookings()
    n = await _bulk_cancel(bot, items)
    await callback.message.answer(f"✅ Отменено записей: <b>{n}</b>")
    await callback.answer()


@router.message(Command("cancel_id"))
async def cmd_cancel_id(message: Message, bot: Bot):
    """Cancel by booking id: /cancel_id 1234567890"""
    if not is_admin(message.from_user.id):
        return
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Синтаксис: <code>/cancel_id ID</code>\nID видно в /bookings")
        return
    booking_id = parts[1].strip()
    from src.services import settings_store as store
    b = store.cancel_booking(booking_id, by="barber")
    if not b:
        await message.answer("Запись не найдена или уже отменена.")
        return
    try:
        from src.services import calendar as gcal
        eid = b.get("calendar_event_id")
        if eid:
            gcal.delete_event(eid)
    except Exception:
        pass
    try:
        await bot.send_message(
            int(b["user_id"]),
            f"❌ Запись на <b>{b.get('date')}</b> отменена барбером.\n"
            f"Можно выбрать другое время через /book.",
        )
    except Exception as e:
        logger.error(f"cancel_id notify: {e}")
    await message.answer(
        f"✅ Отменено: {b.get('date')} — {b.get('client_name') or b.get('user_id')}\n"
        f"💬 {b.get('comment')}"
    )
