from pathlib import Path
import os
from datetime import datetime, timedelta

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from loguru import logger

from src.keyboards.client import main_menu_kb, language_kb, day_selection_kb, service_selection_kb, slot_selection_kb

router = Router()

WELCOME_IMAGE = Path("assets/welcome.png")
ADMIN_GROUP_ID = os.getenv("ADMIN_GROUP_ID")

def _admin_ids() -> list[int]:
    ids = []
    for x in (os.getenv("ADMIN_IDS") or "").split(","):
        x = x.strip()
        if x.isdigit():
            ids.append(int(x))
    return ids


async def _ensure_admin_cb(callback: CallbackQuery) -> bool:
    """Only ADMIN_IDS may use group admin buttons (confirm / reject / cancel / set name)."""
    if callback.from_user and callback.from_user.id in _admin_ids():
        return True
    await callback.answer(
        "⛔ Только админы (вы и барбер) могут нажать эту кнопку.",
        show_alert=True,
    )
    return False




class BookingStates(StatesGroup):
    waiting_slot = State()
    waiting_service = State()
    waiting_comment = State()
    waiting_custom_date = State()
    waiting_contact_name = State()  # admin sets "name in contacts"
    reschedule_date = State()
    reschedule_custom_date = State()
    reschedule_comment = State()
    admin_suggest = State()  # barber types alternative time after reject
    admin_edit = State()  # barber edits confirmed booking


def get_lang(message: Message) -> str:
    code = (message.from_user.language_code or "ru").lower()
    return "lv" if code.startswith("lv") else "ru"


def day_label(day_key: str, lang: str = "ru") -> str:
    mapping = {
        "today": ("Сегодня", "Šodien"),
        "tomorrow": ("Завтра", "Rīt"),
        "day_after": ("Послезавтра", "Parīt"),
        "other": ("Другая дата", "Cita datums"),
    }
    return mapping.get(day_key, (day_key, day_key))[0 if lang == "ru" else 1]


def to_display(d) -> str:
    """Return DD/MM/YYYY"""
    if isinstance(d, str):
        # already display or iso
        if "/" in d:
            return d
        try:
            from datetime import datetime as dt
            return dt.strptime(d, "%Y-%m-%d").strftime("%d/%m/%Y")
        except Exception:
            return d
    return d.strftime("%d/%m/%Y")


def parse_ddmmyyyy(text: str):
    """Parse DD/MM/YYYY or DD.MM.YYYY → date object or None"""
    text = text.strip().replace(".", "/")
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def resolve_date(day_key: str) -> str:
    """Return date as DD/MM/YYYY in bot timezone (Europe/Riga)."""
    try:
        from src.services import calendar as gcal
        today = gcal.now_local().date()
    except Exception:
        today = datetime.now().date()
    if day_key == "today":
        d = today
    elif day_key == "tomorrow":
        d = today + timedelta(days=1)
    elif day_key == "day_after":
        d = today + timedelta(days=2)
    else:
        return "—"
    return to_display(d)


# ---------- Start ----------

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    lang = get_lang(message)
    try:
        from src.services import settings_store as store
        store.track_event("start", message.from_user.id)
        store.save_client_username(message.from_user.id, message.from_user.username)
    except Exception:
        pass
    from src.services import settings_store as store

    # Welcome text from /settings if set, otherwise default
    custom = store.get_welcome_text(lang)
    privacy_ru = (
        "\n\n🔒 Данные (имя, комментарии к записи, история визитов) нужны только "
        "для записи к барберу и связи с вами. Третьим лицам не передаём."
    )
    privacy_lv = (
        "\n\n🔒 Dati (vārds, pieraksta komentāri, vizīšu vēsture) nepieciešami tikai "
        "pierakstam un saziņai. Trešajām personām netiek nodoti."
    )
    defaults = {
        "ru": (
            "Запись к Лучшему Барберу, Парикмахеру и Другу — без звонков и ожидания!\n\n"
            "🗓️ Выберите день (сегодня / завтра / послезавтра)\n"
            "⌚️ Выберите свободное время — бот показывает окна из календаря\n"
            "닦다 Выберите услугу\n"
            "☑️ Получите подтверждение от барбера\n\n"
            "💈 Адрес: Jasmuižas iela 9, Rīga\n"
            "Языки: русский и латышский\n\n"
            "Просто нажмите Start и выбирайте, что актуально.\n\n"
            "Важно: бот отправляет напоминания за 24 часа до записи и в тот же день. "
            "Если подтвердите в первый раз — утром того же дня оповещения не будет."
            + privacy_ru
        ),
        "lv": (
            "Reģistrējieties pie labākā bārddziņa, friziera un drauga — bez zvaniem un gaidīšanas!\n\n"
            "🗓️ Izvēlieties dienu (šodien / rīt / parīt)\n"
            "⌚️ Izvēlieties brīvo laiku — bots rāda logus no kalendāra\n"
            "💇 Izvēlieties pakalpojumu\n"
            "☑️ Saņemiet apstiprinājumu no bārddziņa\n\n"
            "💈 Adrese: Jasmuižas iela 9, Rīga\n"
            "Valodas: krievu un latviešu\n\n"
            "Vienkārši nospiediet Start un izvēlieties to, kas jums ir aktuāli.\n\n"
            "Svarīgi: bots nosūta atgādinājumus 24 stundas pirms rezervācijas un tajā pašā dienā. "
            "Ja apstiprināsiet pirmo reizi, tajā pašā rītā atgādinājums netiks nosūtīts."
            + privacy_lv
        ),
    }

    # Use custom only if it was actually saved (not the short built-in fallback)
    short_fallback_ru = "Привет! Я бот барбершопа. Здесь можно быстро записаться."
    short_fallback_lv = "Sveiki! Esmu frizētavas bots. Šeit var ātri pierakstīties."
    if custom and custom not in (short_fallback_ru, short_fallback_lv):
        caption = custom.strip()
        # Append privacy only if not already present (e.g. pasted full text via /settings)
        marker = "Третьим лицам не передаём" if lang == "ru" else "Trešajām personām netiek nodoti"
        if marker not in caption:
            caption = caption + (privacy_ru if lang == "ru" else privacy_lv)
    else:
        caption = defaults[lang]

    if WELCOME_IMAGE.exists():
        photo = FSInputFile(WELCOME_IMAGE)
        await message.answer_photo(photo=photo, caption=caption, reply_markup=main_menu_kb(lang))
    else:
        await message.answer(caption, reply_markup=main_menu_kb(lang))
    try:
        from src.services import settings_store as store
        banner = store.format_away_banner(lang)
        if banner:
            await message.answer(banner)
    except Exception:
        pass



async def _deny_if_closed_or_full(
    message_or_cb, date_str: str, lang: str, *, as_callback: bool, user_id: int | None = None
) -> bool:
    """Return True if day is blocked/vacation for this user. VIP may pass (request for review)."""
    from src.services import settings_store as store
    if not store.is_blocked(date_str):
        return False
    if user_id and store.is_vip(user_id):
        return False
    msg = store.client_unavailable_message(date_str, lang)
    if as_callback:
        await message_or_cb.message.edit_text(msg)
        await message_or_cb.answer()
    else:
        await message_or_cb.answer(msg)
    return True


async def _offer_slots(target, state: FSMContext, date_str: str, lang: str, *, edit: bool, user_id: int | None = None):
    """Show free slots; VIP also sees busy slots marked ⭐ (normals never see stars)."""
    from src.services import calendar as gcal
    from src.services import settings_store as store
    vip = bool(user_id and store.is_vip(user_id))
    if vip:
        grid = gcal.get_slot_grid(date_str, include_busy=True)
        slots = [t for t, _ in grid]
        busy_slots = [t for t, busy in grid if busy]
    else:
        slots = gcal.get_available_slots(date_str)
        busy_slots = []
    if not slots:
        nl = chr(10)
        text = (
            f"На <b>{date_str}</b> свободных окон нет (календарь занят или вне рабочих часов).{nl}"
            f"Выберите другой день."
            if lang == "ru"
            else f"<b>{date_str}</b> — nav brīvu laiku.{nl}Izvēlieties citu dienu."
        )
        kb = day_selection_kb(lang, vip=vip)
        if edit:
            await target.edit_text(text, reply_markup=kb)
        else:
            await target.answer(text, reply_markup=kb)
        return False
    await state.update_data(date=date_str, slot=None, vip=vip, day_closed=store.is_blocked(date_str))
    await state.set_state(BookingStates.waiting_slot)
    nl = chr(10)
    if lang == "ru":
        text = f"Дата: <b>{date_str}</b>{nl}Выберите время"
        if vip and busy_slots:
            text += f"{nl}<i>⭐ — уже занято в календаре; VIP может запросить это окно на рассмотрение</i>"
        if store.is_blocked(date_str) and vip:
            text += f"{nl}<i>День закрыт для обычной записи — заявка уйдёт барберу на ревью</i>"
    else:
        text = f"Datums: <b>{date_str}</b>{nl}Izvēlieties laiku"
        if vip and busy_slots:
            text += f"{nl}<i>⭐ — aizņemts; VIP var nosūtīt pieprasījumu</i>"
    markup = slot_selection_kb(slots, lang, busy_slots=busy_slots if vip else None)
    if edit:
        await target.edit_text(text, reply_markup=markup)
    else:
        await target.answer(text, reply_markup=markup)
    return True


# ---------- Book ----------

@router.message(Command("book", "start_booking"))
@router.message(F.text.in_({"📅 Записаться", "📅 Pierakstīties"}))
async def cmd_book(message: Message, state: FSMContext):
    await state.clear()
    lang = get_lang(message)
    from src.services import settings_store as store
    vip = store.is_vip(message.from_user.id)
    banner = store.format_away_banner(lang)
    if banner:
        await message.answer(banner)
    text = "Выберите день:" if lang == "ru" else "Izvēlieties dienu:"
    await message.answer(text, reply_markup=day_selection_kb(lang, vip=vip))


async def _apply_reschedule_day(callback: CallbackQuery, state: FSMContext, day_key: str):
    """Reschedule: pick day then same calendar slots as /book."""
    lang_code = (callback.from_user.language_code or "ru").lower()
    lang = "lv" if lang_code.startswith("lv") else "ru"
    from src.services import settings_store as store

    if day_key == "other":
        await state.set_state(BookingStates.reschedule_custom_date)
        await callback.message.edit_text(
            "Введите новую дату <b>ДД/ММ/ГГГГ</b>" if lang == "ru"
            else "Ievadiet jauno datumu <b>DD/MM/GGGG</b>"
        )
        await callback.answer()
        return

    date_str = resolve_date(day_key)
    if store.is_blocked(date_str):
        await callback.message.edit_text(store.client_unavailable_message(date_str, lang))
        await callback.answer()
        return
    await state.update_data(
        reschedule_date=date_str,
        reschedule_day_key=day_key,
        date=date_str,
        day_key=day_key,
    )
    await _offer_slots(callback.message, state, date_str, lang, edit=True)
    await callback.answer()


@router.callback_query(F.data.startswith("day:"))
async def process_day(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    lang_code = (callback.from_user.language_code or "ru").lower()
    lang = "lv" if lang_code.startswith("lv") else "ru"

    # Unavailable day chip (Telegram cannot disable buttons — alert only)
    if len(parts) >= 2 and parts[1] == "na":
        reason = parts[3] if len(parts) > 3 else "no_slots"
        if lang == "ru":
            texts = {
                "blocked": "Этот день закрыт (отпуск / блок).",
                "past": "На сегодня свободных окон уже нет — выберите другой день.",
                "no_slots": "В этот день нет свободного времени (календарь занят).",
            }
            msg = texts.get(reason, "Этот день недоступен для записи.")
        else:
            texts = {
                "blocked": "Šī diena ir slēgta (atvaļinājums / bloks).",
                "past": "Šodien brīvu laiku vairs nav — izvēlieties citu dienu.",
                "no_slots": "Šajā dienā nav brīva laika (kalendārs aizņemts).",
            }
            msg = texts.get(reason, "Šī diena nav pieejama.")
        await callback.answer(msg, show_alert=True)
        return

    current = await state.get_state()
    if current == BookingStates.reschedule_date.state:
        day_key = parts[1]
        await _apply_reschedule_day(callback, state, day_key)
        return
    if current in (
        BookingStates.reschedule_custom_date.state,
        BookingStates.reschedule_comment.state,
    ):
        await callback.answer()
        return

    day_key = parts[1]
    if day_key == "other":
        await state.update_data(day_key="other")
        await state.set_state(BookingStates.waiting_custom_date)
        prompt = (
            "Введите дату в формате <b>ДД/ММ/ГГГГ</b>\n"
            "Например: 25/08/2026"
            if lang == "ru"
            else "Ievadiet datumu formātā <b>DD/MM/GGGG</b>\n"
            "Piemēram: 25/08/2026"
        )
        await callback.message.edit_text(prompt)
        await callback.answer()
        return

    date_str = resolve_date(day_key)
    uid = callback.from_user.id if callback.from_user else None
    if await _deny_if_closed_or_full(callback, date_str, lang, as_callback=True, user_id=uid):
        return
    from src.services import calendar as gcal
    from src.services import settings_store as store
    ok, reason = gcal.day_is_bookable(date_str)
    vip = bool(uid and store.is_vip(uid))
    if not ok and not vip:
        if lang == "ru":
            msg = (
                "На сегодня окон уже нет." if reason == "past"
                else "В этот день нет свободного времени."
            )
        else:
            msg = "Šajā dienā nav brīva laika."
        await callback.answer(msg, show_alert=True)
        return

    await state.update_data(day_key=day_key, date=date_str, day_closed=store.is_blocked(date_str))
    await _offer_slots(callback.message, state, date_str, lang, edit=True, user_id=uid)
    await callback.answer()


@router.message(BookingStates.waiting_custom_date)
async def process_custom_date(message: Message, state: FSMContext):
    lang = get_lang(message)
    parsed = parse_ddmmyyyy(message.text or "")
    if not parsed:
        msg = (
            "Не понял дату. Введите в формате <b>ДД/ММ/ГГГГ</b>\n"
            "Например: 25/08/2026"
            if lang == "ru"
            else "Nesapratu datumu. Ievadiet formātā <b>DD/MM/GGGG</b>\n"
            "Piemēram: 25/08/2026"
        )
        await message.answer(msg)
        return

    date_str = to_display(parsed)
    uid = message.from_user.id if message.from_user else None
    if await _deny_if_closed_or_full(message, date_str, lang, as_callback=False, user_id=uid):
        return

    from src.services import settings_store as store
    await state.update_data(day_key="other", date=date_str, day_closed=store.is_blocked(date_str))
    await _offer_slots(message, state, date_str, lang, edit=False, user_id=uid)





@router.callback_query(BookingStates.waiting_slot, F.data.startswith("slot:"))
async def process_slot(callback: CallbackQuery, state: FSMContext):
    lang_code = (callback.from_user.language_code or "ru").lower()
    lang = "lv" if lang_code.startswith("lv") else "ru"
    key = callback.data.split(":", 1)[1]
    data0 = await state.get_data()
    is_reschedule = bool(data0.get("reschedule_id"))

    if key == "back":
        if is_reschedule:
            await state.set_state(BookingStates.reschedule_date)
        else:
            await state.set_state(None)
        await callback.message.edit_text(
            "Выберите день:" if lang == "ru" else "Izvēlieties dienu:",
            reply_markup=day_selection_kb(lang),
        )
        await callback.answer()
        return

    slot = key
    data = await state.get_data()
    date_str = data.get("date") or data.get("reschedule_date") or ""
    from src.services import calendar as gcal
    from src.services import settings_store as store
    vip = store.is_vip(callback.from_user.id)
    free = gcal.get_available_slots(date_str, use_cache=False)
    slot_busy = slot not in free
    if slot_busy and not vip:
        await callback.answer(
            "Это время уже занято, выберите другое" if lang == "ru" else "Laiks aizņemts",
            show_alert=True,
        )
        await _offer_slots(
            callback.message, state, date_str, lang, edit=True, user_id=callback.from_user.id
        )
        return

    await state.update_data(slot=slot, slot_busy=slot_busy)
    if is_reschedule:
        await state.update_data(reschedule_date=date_str)
        await state.set_state(BookingStates.reschedule_comment)
        nl = chr(10)
        if lang == "ru":
            msg = "Перенос на <b>%s</b> · <b>%s</b>%s%sКомментарий (или «-»):" % (date_str, slot, nl, nl)
        else:
            msg = "Pārcelšana: <b>%s</b> · <b>%s</b>%s%sKomentārs (vai «-»):" % (date_str, slot, nl, nl)
        await callback.message.edit_text(msg)
        await callback.answer()
        return

    await state.set_state(BookingStates.waiting_service)
    nl = chr(10)
    if lang == "ru":
        text_msg = "Дата: <b>%s</b> · время: <b>%s</b>%s%sВыберите услугу:" % (date_str, slot, nl, nl)
    else:
        text_msg = "Datums: <b>%s</b> · laiks: <b>%s</b>%s%sIzvēlieties pakalpojumu:" % (date_str, slot, nl, nl)
    await callback.message.edit_text(text_msg, reply_markup=service_selection_kb(lang))
    await callback.answer()


@router.callback_query(BookingStates.waiting_service, F.data.startswith("svc:"))
async def process_service(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Listed service → send request immediately. Skip → one line custom service name then send."""
    lang_code = (callback.from_user.language_code or "ru").lower()
    lang = "lv" if lang_code.startswith("lv") else "ru"
    from src.services import settings_store as store
    sid = callback.data.split(":", 1)[1]
    service_name = ""
    service_id = ""
    if sid != "skip":
        svc = store.get_service_by_id(sid)
        if svc:
            service_id = sid
            service_name = svc.get("name_ru") if lang == "ru" else svc.get("name_lv")
            service_name = service_name or sid
        await state.update_data(service_id=service_id, service_name=service_name or "")
        await callback.answer()
        await _finish_booking_request(
            callback.from_user,
            state,
            bot,
            raw_comment="",
            reply_target=callback.message,
            lang=lang,
        )
        return
    # Custom / skip: short text for service only (not a free comment step)
    await state.update_data(service_id="", service_name="")
    await state.set_state(BookingStates.waiting_comment)
    await callback.message.edit_text(
        "Напишите услугу одним сообщением (или «-» чтобы без названия):"
        if lang == "ru"
        else "Uzrakstiet pakalpojumu vienā ziņā (vai «-» bez nosaukuma):"
    )
    await callback.answer()



async def _finish_booking_request(user, state: FSMContext, bot: Bot, *, raw_comment: str, reply_target, lang: str):
    """Shared submit after service: optional free-text note."""
    data = await state.get_data()
    day_key = data.get("day_key", "—")
    date_str = data.get("date", "—")
    slot = data.get("slot") or ""
    raw = (raw_comment or "").strip()
    if raw in ("", "—", "-"):
        raw = ""
    if slot:
        comment = f"{slot}" + (f" · {raw}" if raw else "")
    else:
        comment = raw or "—"
    service_id = data.get("service_id") or ""
    service_name = data.get("service_name") or ""
    from src.services import settings_store as store

    if store.is_blocked(date_str) and not store.is_vip(user.id):
        await state.clear()
        await reply_target.answer(
            store.client_unavailable_message(date_str, lang),
            reply_markup=main_menu_kb(lang),
        )
        return

    await state.clear()
    extracted = slot or store.extract_time_hint(comment)
    day_name = day_label(day_key, lang)
    nl = chr(10)
    svc_line = f"{nl}Услуга: <b>{service_name}</b>" if service_name else ""
    time_line = f"{nl}Время: <b>{extracted}</b>" if extracted else ""
    if lang == "ru":
        client_text = (
            f"✅ Заявка отправлена!{nl}{nl}"
            f"День: <b>{day_name}</b> ({date_str})"
            + svc_line
            + time_line
            + f"{nl}{nl}Барбер скоро подтвердит или предложит другое время."
        )
    else:
        svc_lv = f"{nl}Pakalpojums: <b>{service_name}</b>" if service_name else ""
        time_lv = f"{nl}Laiks: <b>{extracted}</b>" if extracted else ""
        client_text = (
            f"✅ Pieprasījums nosūtīts!{nl}{nl}"
            f"Diena: <b>{day_name}</b> ({date_str})"
            + svc_lv
            + time_lv
            + f"{nl}{nl}Bārddzinis drīz apstiprinās vai piedāvās citu laiku."
        )
    withdraw_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="↩️ Отозвать заявку" if lang == "ru" else "↩️ Atcelt pieteikumu",
            callback_data="pend:withdraw",
        )]
    ])
    # Reply keyboard (main menu) stays; this adds inline withdraw under the success text
    await reply_target.answer(client_text, reply_markup=withdraw_kb)

    if ADMIN_GROUP_ID:
        client_line = store.format_client_line(user.id, user.full_name, ref_date=date_str)
        vip = store.is_vip(user.id)
        slot_busy = bool(data.get("slot_busy"))
        day_closed = bool(data.get("day_closed") or store.is_blocked(date_str))
        # Minimal VIP mark: only when override (busy slot or closed day) — no clutter for normal VIP visits
        override = vip and (slot_busy or day_closed)
        title = "🆕 <b>Новая заявка</b>"
        if override:
            title = "🆕 <b>Новая заявка</b> · <b>VIP</b> (исключение)"
        group_text = (
            f"{title}{nl}{nl}"
            f"{client_line}{nl}"
            f"📅 День: <b>{day_label(day_key, 'ru')}</b> ({date_str}){nl}"
        )
        if service_name:
            group_text += f"✂️ Услуга: <b>{service_name}</b>{nl}"
        if extracted:
            mark = " ⚠️ занято в Calendar" if slot_busy else ""
            group_text += f"🕐 Время: <b>{extracted}</b>{mark}{nl}"
        if day_closed:
            group_text += f"🔒 День закрыт (блок/отпуск) — только на ревью{nl}"
        # No separate comment line: slot + service already cover the request
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"adm:ok:{user.id}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"adm:no:{user.id}"),
            ],
            [
                InlineKeyboardButton(
                    text="💬 Написать клиенту",
                    url=store.client_chat_url(user.id, user.username),
                ),
                InlineKeyboardButton(
                    text="📝 Имя в контактах",
                    callback_data=f"adm:setname:{user.id}",
                ),
            ],
        ])
        try:
            store.save_client_username(user.id, user.username)
            store.save_pending_booking(
                user.id,
                date_str,
                comment,
                client_name=user.full_name or "",
                kind="book",
                service_id=service_id,
                service_name=service_name,
                extracted_time=extracted,
            )
            store.track_event("book_request", user.id)
            sent = await bot.send_message(ADMIN_GROUP_ID, group_text, reply_markup=kb)
            try:
                store.set_pending_group_message(user.id, sent.message_id)
            except Exception:
                pass
            notice = store.maybe_notify_day_almost_full(date_str)
            if notice:
                await bot.send_message(ADMIN_GROUP_ID, notice)
            logger.info(f"Booking request from {user.id} sent to group")
        except Exception as e:
            logger.error(f"Failed to send booking to group: {e}")
            await reply_target.answer(
                "Заявка принята, но не удалось уведомить барбера." if lang == "ru"
                else "Pieprasījums pieņemts, bet neizdevās paziņot."
            )


@router.callback_query(BookingStates.waiting_comment, F.data == "comment:skip")
async def process_comment_skip(callback: CallbackQuery, state: FSMContext, bot: Bot):
    lang_code = (callback.from_user.language_code or "ru").lower()
    lang = "lv" if lang_code.startswith("lv") else "ru"
    await callback.answer()
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await _finish_booking_request(
        callback.from_user,
        state,
        bot,
        raw_comment="",
        reply_target=callback.message,
        lang=lang,
    )


@router.message(BookingStates.waiting_comment)
async def process_comment(message: Message, state: FSMContext, bot: Bot):
    """Only used after «Пропустить / свой текст» — text becomes service name, then send."""
    lang = get_lang(message)
    raw = (message.text or "").strip()
    if raw in ("", "—", "-"):
        await state.update_data(service_name="", service_id="")
    else:
        await state.update_data(service_name=raw, service_id="")
    await _finish_booking_request(
        message.from_user,
        state,
        bot,
        raw_comment="",
        reply_target=message,
        lang=lang,
    )




@router.callback_query(F.data == "pend:withdraw")
async def client_withdraw_pending(callback: CallbackQuery, bot: Bot):
    """Client revokes pending request before barber confirms."""
    lang_code = (callback.from_user.language_code or "ru").lower()
    lang = "lv" if lang_code.startswith("lv") else "ru"
    from src.services import settings_store as store
    uid = callback.from_user.id
    pending = store.get_pending_booking(uid)
    if not pending:
        await callback.answer(
            "Заявка уже обработана или отозвана." if lang == "ru"
            else "Pieteikums jau apstrādāts vai atcelts.",
            show_alert=True,
        )
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        return
    data = store.pop_pending_booking(uid)
    await callback.answer("Отозвано" if lang == "ru" else "Atcelts")
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    text = (
        "↩️ Заявка отозвана. Можно записаться снова через /book."
        if lang == "ru"
        else "↩️ Pieteikums atcelts. Varat pierakstīties no jauna ar /book."
    )
    await callback.message.answer(text, reply_markup=main_menu_kb(lang))
    if ADMIN_GROUP_ID and data:
        try:
            line = store.format_client_line(uid, callback.from_user.full_name)
            nl = chr(10)
            note = (
                f"↩️ <b>Клиент отозвал заявку</b>{nl}"
                f"{line}{nl}"
                f"📅 {data.get('date')} · {data.get('extracted_time') or ''}{nl}"
                f"💬 {data.get('comment')}"
            )
            mid = data.get("group_message_id")
            if mid:
                try:
                    await bot.edit_message_text(
                        chat_id=ADMIN_GROUP_ID,
                        message_id=int(mid),
                        text=note + nl + nl + "<i>Кнопки сняты — заявка отозвана клиентом.</i>",
                        reply_markup=None,
                    )
                except Exception:
                    await bot.send_message(ADMIN_GROUP_ID, note)
            else:
                await bot.send_message(ADMIN_GROUP_ID, note)
        except Exception as e:
            logger.error(f"withdraw notify group: {e}")
    try:
        store.track_event("pending_withdraw", uid)
    except Exception:
        pass


@router.message(Command("cancel"))
@router.message(F.text.lower().in_({"отменить", "отмена", "cancel", "atcelt"}))
async def cmd_cancel(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    lang = get_lang(message)
    text = (
        "Хорошо, текущее действие отменено.\n"
        "Чтобы отменить уже подтверждённую запись — /cancel_booking"
        if lang == "ru"
        else "Labi, darbība atcelta.\n"
        "Lai atceltu apstiprinātu pierakstu — /cancel_booking"
    )
    await message.answer(text, reply_markup=main_menu_kb(lang))


@router.message(Command("cancel_booking"))
@router.message(F.text.in_({"❌ Отменить запись", "❌ Atcelt pierakstu"}))
async def cmd_cancel_booking(message: Message, bot: Bot):
    """Client cancels an active confirmed appointment (pick if several)."""
    from src.services import settings_store as store
    lang = get_lang(message)
    active = store.get_active_bookings_for_user(message.from_user.id)
    if not active:
        await message.answer(
            "Нет активных записей для отмены." if lang == "ru"
            else "Nav aktīvu pierakstu."
        )
        return

    if len(active) == 1:
        await _do_client_cancel(message, bot, active[-1], lang)
        return

    await message.answer(
        "Несколько записей. Выберите, какую отменить:" if lang == "ru"
        else "Vairāki pieraksti. Izvēlieties, kuru atcelt:"
    )
    for b in active:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=f"❌ {b.get('date')} — отменить",
                callback_data=f"cli:cancel:{b.get('id')}",
            )]
        ])
        await message.answer(
            f"📅 {b.get('date')}\n💬 {b.get('comment')}",
            reply_markup=kb,
        )


async def _do_client_cancel(message_or_cb, bot: Bot, b: dict, lang: str):
    from src.services import settings_store as store
    # Refresh and refuse if barber already cancelled
    fresh = store.get_booking(b["id"])
    if not fresh or fresh.get("status") != "confirmed":
        text = (
            "Эта запись уже отменена." if lang == "ru"
            else "Šis pieraksts jau ir atcelts."
        )
        if hasattr(message_or_cb, "answer") and not hasattr(message_or_cb, "message"):
            await message_or_cb.answer(text)
        else:
            await message_or_cb.message.answer(text)
        return
    result = store.cancel_booking(b["id"], by="client")
    if result.get("ok"):
        try:
            store.track_event("cancel_client", int(b.get("user_id") or 0))
        except Exception:
            pass
    if not result.get("ok"):
        text = (
            "Эта запись уже отменена." if lang == "ru"
            else "Šis pieraksts jau ir atcelts."
        )
        if hasattr(message_or_cb, "answer") and not hasattr(message_or_cb, "message"):
            await message_or_cb.answer(text)
        else:
            await message_or_cb.message.answer(text)
        return
    b = result["booking"]
    try:
        from src.services import calendar as gcal
        eid = b.get("calendar_event_id")
        if eid:
            gcal.delete_event(eid)
    except Exception:
        pass
    text = (
        f"✅ Вы отменили запись на <b>{b.get('date')}</b>.\n"
        f"Можно записаться снова через /book."
        if lang == "ru"
        else f"✅ Jūs atcēlāt pierakstu uz <b>{b.get('date')}</b>.\n"
        f"Varat pierakstīties no jauna ar /book."
    )
    if hasattr(message_or_cb, "answer") and not hasattr(message_or_cb, "message"):
        await message_or_cb.answer(text)
        user = message_or_cb.from_user
    else:
        await message_or_cb.message.answer(text)
        user = message_or_cb.from_user
    if ADMIN_GROUP_ID:
        try:
            line = store.format_client_line(user.id, user.full_name)
            await bot.send_message(
                ADMIN_GROUP_ID,
                f"❌ <b>Клиент отменил запись</b>\n"
                f"{line}\n"
                f"📅 Дата: {b.get('date')}\n"
                f"💬 {b.get('comment')}",
            )
            await _clear_group_cancel_button(bot, b)
        except Exception as e:
            logger.error(f"cancel_booking group notify: {e}")


@router.callback_query(F.data.startswith("cli:cancel:"))
async def client_cancel_pick(callback: CallbackQuery, bot: Bot):
    booking_id = callback.data.split(":")[2]
    from src.services import settings_store as store
    b = store.get_booking(booking_id)
    if not b or b.get("status") != "confirmed":
        await callback.answer("Уже отменено", show_alert=True)
        return
    if int(b.get("user_id", 0)) != callback.from_user.id:
        await callback.answer("Нет доступа", show_alert=True)
        return
    lang = "ru"
    await _do_client_cancel(callback, bot, b, lang)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("Отменено")



# ---------- Reschedule ----------

@router.message(Command("reschedule"))
@router.message(F.text.in_({"📅 Перенести запись", "📅 Pārcelt pierakstu"}))
async def cmd_reschedule(message: Message, state: FSMContext):
    from src.services import settings_store as store
    await state.clear()
    lang = get_lang(message)
    active = store.get_active_bookings_for_user(message.from_user.id)
    if not active:
        await message.answer(
            "Нет активных записей для переноса." if lang == "ru"
            else "Nav aktīvu pierakstu, ko pārcelt."
        )
        return
    if len(active) == 1:
        await state.update_data(reschedule_id=active[-1]["id"])
        await state.set_state(BookingStates.reschedule_date)
        await message.answer(
            f"Перенос записи на <b>{active[-1].get('date')}</b>.\nВыберите новый день:"
            if lang == "ru"
            else f"Pārcelšana: <b>{active[-1].get('date')}</b>.\nIzvēlieties jaunu dienu:",
            reply_markup=day_selection_kb(lang),
        )
        return
    await message.answer(
        "Выберите запись для переноса:" if lang == "ru" else "Izvēlieties pierakstu:"
    )
    for b in active:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=f"📅 {b.get('date')} — перенести",
                callback_data=f"cli:resched:{b.get('id')}",
            )]
        ])
        await message.answer(
            f"📅 {b.get('date')}\n💬 {b.get('comment')}",
            reply_markup=kb,
        )


@router.callback_query(F.data.startswith("cli:resched:"))
async def client_resched_pick(callback: CallbackQuery, state: FSMContext):
    booking_id = callback.data.split(":")[2]
    from src.services import settings_store as store
    b = store.get_booking(booking_id)
    if not b or b.get("status") != "confirmed":
        await callback.answer("Запись недоступна", show_alert=True)
        return
    if int(b.get("user_id", 0)) != callback.from_user.id:
        await callback.answer("Нет доступа", show_alert=True)
        return
    lang = "ru"
    await state.update_data(reschedule_id=booking_id)
    await state.set_state(BookingStates.reschedule_date)
    await callback.message.answer(
        f"Перенос записи на <b>{b.get('date')}</b>.\nВыберите новый день:",
        reply_markup=day_selection_kb(lang),
    )
    await callback.answer()


@router.callback_query(BookingStates.reschedule_date, F.data.startswith("day:"))
async def reschedule_day(callback: CallbackQuery, state: FSMContext):
    day_key = callback.data.split(":")[1]
    await _apply_reschedule_day(callback, state, day_key)


@router.message(BookingStates.reschedule_custom_date)
async def reschedule_custom_date(message: Message, state: FSMContext):
    from src.services import settings_store as store
    lang = get_lang(message)
    parsed = parse_ddmmyyyy(message.text or "")
    if not parsed:
        await message.answer("Формат: <b>ДД/ММ/ГГГГ</b>")
        return
    date_str = to_display(parsed)
    if store.is_blocked(date_str):
        await message.answer(store.client_unavailable_message(date_str, lang))
        return
    await state.update_data(
        reschedule_date=date_str,
        reschedule_day_key="other",
        date=date_str,
        day_key="other",
    )
    await _offer_slots(message, state, date_str, lang, edit=False)


@router.message(BookingStates.reschedule_comment)
async def reschedule_comment(message: Message, state: FSMContext, bot: Bot):
    """Send reschedule request to admin group — same as /book (needs accept/reject)."""
    from src.services import settings_store as store
    lang = get_lang(message)
    data = await state.get_data()
    booking_id = data.get("reschedule_id")
    new_date = data.get("reschedule_date")
    slot = data.get("slot") or ""
    raw = (message.text or "").strip() or "—"
    if slot:
        comment = f"{slot}" + (f" · {raw}" if raw not in ("—", "-", "") else "")
    else:
        comment = raw
    await state.clear()
    if not booking_id or not new_date:
        await message.answer("Сессия сброшена. Начните снова: /reschedule")
        return
    existing = store.get_booking(booking_id)
    if not existing or existing.get("status") != "confirmed":
        await message.answer(
            "Запись уже недоступна для переноса." if lang == "ru"
            else "Pieraksts vairs nav pieejams."
        )
        return
    old_date = existing.get("date", "—")
    user = message.from_user
    store.save_client_username(user.id, user.username)
    store.save_pending_booking(
        user.id,
        new_date,
        comment,
        client_name=user.full_name or "",
        kind="reschedule",  # noqa

        reschedule_id=booking_id,
        old_date=old_date,
    )
    store.track_event("reschedule_request", user.id)
    await message.answer(
        f"✅ Запрос на перенос отправлен!\n\n"
        f"Было: <b>{old_date}</b>\n"
        f"Новая дата: <b>{new_date}</b>\n"
        f"💬 {comment}\n\n"
        f"Ждём подтверждения барбера. Старая запись пока действует."
        if lang == "ru"
        else f"✅ Pārcelšanas pieprasījums nosūtīts!\nVecais: <b>{old_date}</b> → <b>{new_date}</b>",
        reply_markup=main_menu_kb(lang),
    )
    if ADMIN_GROUP_ID:
        try:
            line = store.format_client_line(user.id, user.full_name, ref_date=new_date)
            group_text = (
                f"📅 <b>Запрос на перенос</b>\n\n"
                f"{line}\n"
                f"Было: <b>{old_date}</b>\n"
                f"Новая дата: <b>{new_date}</b>\n"
                f"💬 Комментарий: {comment}\n"
                f"ID: <code>{booking_id}</code>"
            )
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Подтвердить перенос", callback_data=f"adm:ok:{user.id}"),
                    InlineKeyboardButton(text="❌ Отклонить", callback_data=f"adm:no:{user.id}"),
                ],
                [
                    InlineKeyboardButton(text="💬 Написать клиенту", url=store.client_chat_url(user.id, user.username)),
                ],
                [
                    InlineKeyboardButton(text="📝 Имя в контактах", callback_data=f"adm:setname:{user.id}"),
                ],
            ])
            await bot.send_message(ADMIN_GROUP_ID, group_text, reply_markup=kb)
        except Exception as e:
            logger.error(f"reschedule group: {e}")



@router.message(Command("prices", "price"))
@router.message(F.text.in_({"💰 Цены", "💰 Cenas"}))
async def cmd_prices(message: Message):
    from src.services import settings_store as store
    lang = get_lang(message)
    body = store.format_services_text(lang)
    header = "💰 <b>Цены</b>\n\n" if lang == "ru" else "💰 <b>Cenas</b>\n\n"
    await message.answer(header + body)


HIST_PAGE_SIZE = 5


def _history_text(user_id: int, page: int, lang: str) -> tuple[str, InlineKeyboardMarkup | None]:
    from src.services import settings_store as store
    data = store.get_history_page(user_id, page=page, page_size=HIST_PAGE_SIZE)
    if data["total"] == 0:
        body = (
            "📋 Пока история пуста.\nКогда появятся подтверждённые записи, они будут здесь."
            if lang == "ru"
            else "📋 Vēsture pagaidām tukša."
        )
        return body, None
    lines = []
    for e in data["items"]:
        svc = e.get("service", "—")
        dt = e.get("date", "")
        lines.append(f"• {dt + ' — ' if dt else ''}{svc}")
    header = (
        f"📋 Ваша история ({data['total']})\n"
        f"Стр. {data['page'] + 1}/{data['total_pages']}\n\n"
        if lang == "ru"
        else f"📋 Vēsture ({data['total']})\n"
        f"Lpp. {data['page'] + 1}/{data['total_pages']}\n\n"
    )
    kb = None
    if data["total_pages"] > 1:
        nav = []
        if data["page"] > 0:
            nav.append(InlineKeyboardButton(
                text="◀️",
                callback_data=f"hist:p:{data['page'] - 1}",
            ))
        nav.append(InlineKeyboardButton(
            text=f"{data['page'] + 1}/{data['total_pages']}",
            callback_data="hist:noop",
        ))
        if data["page"] < data["total_pages"] - 1:
            nav.append(InlineKeyboardButton(
                text="▶️",
                callback_data=f"hist:p:{data['page'] + 1}",
            ))
        kb = InlineKeyboardMarkup(inline_keyboard=[nav])
    return header + "\n".join(lines), kb


@router.message(Command("history"))
@router.message(F.text.in_({"📋 История записей", "📋 Pierakstu vēsture"}))
async def cmd_history(message: Message):
    lang = get_lang(message)
    body, kb = _history_text(message.from_user.id, page=0, lang=lang)
    await message.answer(body, reply_markup=kb)


@router.callback_query(F.data.startswith("hist:p:"))
async def history_page(callback: CallbackQuery):
    try:
        page = int(callback.data.split(":")[2])
    except Exception:
        page = 0
    lang = "ru"
    body, kb = _history_text(callback.from_user.id, page=page, lang=lang)
    try:
        await callback.message.edit_text(body, reply_markup=kb)
    except Exception:
        await callback.message.answer(body, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "hist:noop")
async def history_noop(callback: CallbackQuery):
    await callback.answer()


@router.message(Command("contact"))
@router.message(F.text.in_({"📞 Связаться", "📞 Sazināties"}))
async def cmd_contact(message: Message):
    lang = get_lang(message)
    text = (
        "📞 Напишите ваш вопрос прямо сюда — сообщение уйдёт барберу в группу.\n\n"
        "🔒 Данные используются только для записи и связи, третьим лицам не передаём."
        if lang == "ru"
        else "📞 Uzrakstiet jautājumu šeit — ziņa aizies frizierim uz grupu.\n\n"
        "🔒 Dati tiek izmantoti tikai pierakstam un saziņai, trešajām personām netiek nodoti."
    )
    await message.answer(text)


@router.message(Command("help"))
async def cmd_help(message: Message):
    lang = get_lang(message)
    if lang == "ru":
        text = (
            "Команды:\n"
            "/start — меню\n"
            "/book — записаться\n"
            "/prices — цены\n"
            "/history — история\n"
            "/contact — связаться\n"
            "/cancel — отменить текущее действие\n"
            "/help — справка"
        )
    else:
        text = (
            "Komandas:\n"
            "/start — izvēlne\n"
            "/book — pierakstīties\n"
            "/prices — cenas\n"
            "/history — vēsture\n"
            "/contact — sazināties\n"
            "/cancel — atcelt\n"
            "/help — palīdzība"
        )
    await message.answer(text)


# ---------- Language ----------

@router.message(F.text.in_({"🌐 Language / Valoda"}))
async def change_language(message: Message):
    await message.answer("Выберите язык / Izvēlieties valodu:", reply_markup=language_kb())


@router.callback_query(F.data.startswith("lang:"))
async def set_language(callback: CallbackQuery):
    lang = callback.data.split(":")[1]
    text = "Язык изменён ✅" if lang == "ru" else "Valoda nomainīta ✅"
    await callback.message.edit_text(text)
    await callback.message.answer(
        "Главное меню:" if lang == "ru" else "Galvenā izvēlne:",
        reply_markup=main_menu_kb(lang),
    )
    await callback.answer()


# ---------- Admin quick replies on booking ----------

@router.callback_query(F.data.startswith("adm:ok:"))
async def admin_confirm(callback: CallbackQuery, bot: Bot):
    if not await _ensure_admin_cb(callback):
        return
    client_id = int(callback.data.split(":")[2])
    from src.services import settings_store as store
    from src.services import calendar as gcal

    pending = store.pop_pending_booking(client_id)
    cal_note = ""
    booking_id = ""
    is_reschedule = bool(pending and pending.get("kind") == "reschedule")

    if pending and is_reschedule:
        rid = pending.get("reschedule_id") or ""
        result = store.reschedule_booking(
            rid,
            pending.get("date") or "",
            pending.get("comment") or "",
        )
        if not result.get("ok"):
            await callback.answer("Не удалось перенести (уже отменено?)", show_alert=True)
            try:
                await callback.message.edit_text(
                    callback.message.text + "\n\n⚠️ Перенос не применён"
                )
            except Exception:
                pass
            return
        booking_id = rid
        store.track_event("reschedule_confirmed", client_id)
        name = pending.get("client_name") or "Клиент"
        contact = store.get_client_contact_name(client_id)
        summary = f"{contact or name} (перенос)"
        desc = (
            f"Telegram: {name}\n"
            f"Комментарий: {pending.get('comment', '')}\n"
            f"Дата: {pending.get('date', '')} (было {pending.get('old_date', '')})"
        )
        event_id = gcal.create_event(
            summary=summary,
            date_str=pending.get("date", ""),
            comment=pending.get("comment", ""),
            duration_min=None,
            description=desc,
            start_time=pending.get("extracted_time") or None,
        )
        if event_id:
            cal_note = "\n📅 Calendar обновлён"
            store.update_booking(booking_id, calendar_event_id=event_id)
        elif gcal.is_configured():
            cal_note = "\n⚠️ Calendar: не удалось создать событие"
    elif pending:
        booking_id = store.add_confirmed_booking(
            client_id,
            pending.get("date") or "",
            pending.get("comment") or "",
            client_name=pending.get("client_name") or "",
            service_id=pending.get("service_id") or "",
            service_name=pending.get("service_name") or "",
            extracted_time=pending.get("extracted_time") or "",
        )
        store.add_service_history(
            client_id,
            pending.get("comment") or "услуга",
            pending.get("date") or "",
            booking_id=booking_id,
        )
        store.track_event("booking_confirmed", client_id)
        name = pending.get("client_name") or "Клиент"
        contact = store.get_client_contact_name(client_id)
        svc = pending.get("service_name") or ""
        summary = f"{contact or name}" + (f" — {svc}" if svc else "")
        desc = (
            f"Telegram: {name}\n"
            f"Комментарий: {pending.get('comment', '')}\n"
            f"Дата: {pending.get('date', '')}"
        )
        event_id = gcal.create_event(
            summary=summary,
            date_str=pending.get("date", ""),
            comment=pending.get("comment", ""),
            duration_min=None,
            description=desc,
            start_time=pending.get("extracted_time") or None,
        )
        if event_id:
            cal_note = "\n📅 Добавлено в Google Calendar"
            store.update_booking(booking_id, calendar_event_id=event_id)
        elif gcal.is_configured():
            cal_note = "\n⚠️ Calendar: не удалось создать событие"

    try:
        location = store.get_location()
        phone = store.get_phone()
        if is_reschedule:
            client_msg = (
                f"✅ Перенос подтверждён!\n"
                f"Новая дата: <b>{pending.get('date')}</b>\n"
                f"💬 {pending.get('comment')}\n\n"
                f"📍 {location}\n"
                f"Если что-то случится: {phone}\n\n"
                f"Отменить: /cancel_booking"
            )
        else:
            client_msg = (
                f"✅ Ваша заявка подтверждена! Ждём вас.\n"
                f"📍 {location}\n"
                f"Если что-то случится, вот телефон: {phone}\n\n"
                f"Отменить запись: /cancel_booking"
            )
        await bot.send_message(client_id, client_msg)
        kb = None
        if booking_id:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="❌ Отменить эту запись",
                    callback_data=f"adm:cancel:{booking_id}",
                )],
            ])
        await callback.message.edit_text(
            callback.message.text + (f"\n\n✅ <b>Перенос подтверждён</b>{cal_note}" if is_reschedule else f"\n\n✅ <b>Подтверждено</b>{cal_note}"),
            reply_markup=kb,
        )
        if booking_id:
            store.update_booking(
                booking_id,
                group_chat_id=callback.message.chat.id,
                group_message_id=callback.message.message_id,
            )
    except Exception as e:
        await callback.answer(f"Не удалось написать клиенту: {e}", show_alert=True)
        return
    await callback.answer("Клиент уведомлён")



@router.callback_query(F.data.startswith("adm:no:"))
async def admin_reject(callback: CallbackQuery, bot: Bot):
    """Reject request but KEEP pending so barber can suggest another time (same ticket)."""
    if not await _ensure_admin_cb(callback):
        return
    client_id = int(callback.data.split(":")[2])
    from src.services import settings_store as store
    pending = store.get_pending_booking(client_id)
    is_reschedule = bool(pending and pending.get("kind") == "reschedule")

    try:
        if is_reschedule:
            # transfer rejected — keep original confirmed booking
            store.pop_pending_booking(client_id)
            await bot.send_message(
                client_id,
                "К сожалению, перенос на это время не можем принять.\n"
                f"Старая запись на <b>{(pending or {}).get('old_date', '…')}</b> остаётся в силе.\n"
                "Можно предложить другой слот через /reschedule или /book.",
            )
            footer = "\n\n❌ <b>Перенос отклонён</b> (старая запись сохранена)"
            await callback.message.edit_text(callback.message.text + footer)
        else:
            if pending:
                store.update_pending_booking(client_id, status="rejected")
            else:
                # nothing to keep — still notify
                pass
            await bot.send_message(
                client_id,
                "К сожалению, это время сейчас не подходит.\n"
                "Барбер может предложить другое — дождитесь сообщения в боте "
                "или напишите удобные окна ответом сюда.",
            )
            footer = "\n\n❌ <b>Отклонено</b> — можно предложить другое время"
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="📅 Предложить другое время",
                    callback_data=f"adm:suggest:{client_id}",
                )],
                [InlineKeyboardButton(
                    text="🗑 Закрыть заявку",
                    callback_data=f"adm:close_ticket:{client_id}",
                )],
            ])
            await callback.message.edit_text(
                callback.message.text + footer, reply_markup=kb
            )
    except Exception as e:
        await callback.answer(f"Ошибка: {e}", show_alert=True)
        return
    await callback.answer("Клиент уведомлён")


@router.callback_query(F.data.startswith("adm:close_ticket:"))
async def admin_close_ticket(callback: CallbackQuery, bot: Bot):
    if not await _ensure_admin_cb(callback):
        return
    client_id = int(callback.data.split(":")[2])
    from src.services import settings_store as store
    store.pop_pending_booking(client_id)
    try:
        await bot.send_message(
            client_id,
            "Заявка закрыта. Когда будете готовы — снова /book.",
        )
    except Exception:
        pass
    try:
        await callback.message.edit_text(
            (callback.message.text or "") + "\n\n🗑 <b>Заявка закрыта</b>",
            reply_markup=None,
        )
    except Exception:
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
    await callback.answer("Закрыто")


@router.callback_query(F.data.startswith("adm:suggest:"))
async def admin_suggest_start(callback: CallbackQuery, state: FSMContext):
    if not await _ensure_admin_cb(callback):
        return
    client_id = int(callback.data.split(":")[2])
    from src.services import settings_store as store
    pending = store.get_pending_booking(client_id)
    hint = ""
    if pending:
        hint = (
            f"\nИсходная заявка: {pending.get('date') or '—'} · "
            f"{pending.get('extracted_time') or ''} · {pending.get('service_name') or ''}"
        )
    await state.set_state(BookingStates.admin_suggest)
    await state.update_data(
        suggest_user_id=client_id,
        suggest_group_msg_id=callback.message.message_id,
        suggest_group_chat_id=callback.message.chat.id,
    )
    await callback.message.answer(
        "Напишите предложение клиенту одним сообщением.\n"
        "Можно свободный текст. Если укажете <b>ЧЧ:ММ</b> (даже 11:20) — "
        "после принятия клиентом это время уйдёт в Calendar.\n"
        "Пример: «Могу 14/10/2026 в 11:20» или «завтра после 15:00»\n"
        f"{hint}\n"
        "/cancel — отмена"
    )
    await callback.answer()


@router.message(BookingStates.admin_suggest, F.text)
async def admin_suggest_send(message: Message, state: FSMContext, bot: Bot):
    if message.from_user.id not in _admin_ids():
        await state.clear()
        return
    if message.text and message.text.startswith("/cancel"):
        await state.clear()
        await message.answer("Отменено.")
        return
    data = await state.get_data()
    uid = data.get("suggest_user_id")
    await state.clear()
    if not uid:
        await message.answer("Сессия сброшена.")
        return
    text_out = (message.text or "").strip()
    if not text_out:
        await message.answer("Пустое сообщение — напишите текстом.")
        return

    from src.services import settings_store as store
    pending = store.get_pending_booking(int(uid))
    fallback_date = (pending or {}).get("date") or ""
    parsed = store.parse_suggestion_fields(text_out, fallback_date=fallback_date)

    # Keep / restore pending ticket with suggestion
    if pending:
        store.update_pending_booking(
            int(uid),
            status="suggested",
            suggestion_text=text_out,
            suggested_date=parsed.get("date") or fallback_date,
            suggested_time=parsed.get("time") or "",
        )
    else:
        # recreate minimal pending so accept can confirm
        store.save_pending_booking(
            user_id=int(uid),
            date_str=parsed.get("date") or fallback_date or "",
            comment=text_out,
            client_name="",
            kind="book",
            extracted_time=parsed.get("time") or "",
        )
        store.update_pending_booking(
            int(uid),
            status="suggested",
            suggestion_text=text_out,
            suggested_date=parsed.get("date") or "",
            suggested_time=parsed.get("time") or "",
        )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Принять это время", callback_data=f"sug:ok:{uid}"),
            InlineKeyboardButton(text="❌ Не подходит", callback_data=f"sug:no:{uid}"),
        ],
    ])
    try:
        await bot.send_message(
            int(uid),
            f"<b>Барбер предлагает другое время:</b>\n\n{text_out}\n\n"
            f"Нажмите кнопку ниже.",
            reply_markup=kb,
        )
        note = ""
        if parsed.get("time"):
            note = f"\n⏱ Для Calendar распознано: <code>{parsed.get('date') or '—'} {parsed['time']}</code>"
        await message.answer("✅ Предложение отправлено клиенту." + note)
    except Exception as e:
        await message.answer(f"Не удалось отправить: {e}")


@router.message(BookingStates.admin_suggest)
async def admin_suggest_nontext(message: Message):
    if message.from_user and message.from_user.id not in _admin_ids():
        return
    await message.answer("Нужен текст предложения (не голос). /cancel — отмена")


@router.callback_query(F.data.startswith("sug:ok:"))
async def client_accept_suggestion(callback: CallbackQuery, bot: Bot):
    """Client accepts barber's alternative time → confirm + Calendar with exact HH:MM."""
    uid = int(callback.data.split(":")[2])
    if callback.from_user.id != uid:
        await callback.answer("Это предложение не для вас.", show_alert=True)
        return
    from src.services import settings_store as store
    from src.services import calendar as gcal

    pending = store.get_pending_booking(uid)
    if not pending or pending.get("status") not in ("suggested", "rejected", None, ""):
        # still allow if status suggested or leftover
        if not pending:
            await callback.answer("Предложение уже не актуально.", show_alert=True)
            try:
                await callback.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass
            return

    pending = store.pop_pending_booking(uid) or pending
    date_str = (
        pending.get("suggested_date")
        or pending.get("date")
        or ""
    )
    time_str = (
        pending.get("suggested_time")
        or pending.get("extracted_time")
        or ""
    )
    # re-parse from suggestion text if time missing
    if not time_str and pending.get("suggestion_text"):
        parsed = store.parse_suggestion_fields(
            pending["suggestion_text"], fallback_date=date_str
        )
        time_str = parsed.get("time") or time_str
        if parsed.get("date"):
            date_str = parsed["date"]

    comment_parts = []
    if time_str:
        comment_parts.append(time_str)
    if pending.get("suggestion_text"):
        comment_parts.append(pending["suggestion_text"])
    elif pending.get("comment"):
        comment_parts.append(pending["comment"])
    comment = " · ".join(comment_parts) if comment_parts else (time_str or "—")

    booking_id = store.add_confirmed_booking(
        user_id=uid,
        date_str=date_str,
        comment=comment,
        client_name=pending.get("client_name") or callback.from_user.full_name or "",
        service_id=pending.get("service_id") or "",
        service_name=pending.get("service_name") or "",
        extracted_time=time_str or "",
    )
    store.add_service_history(
        uid,
        pending.get("service_name") or "визит",
        date_str=date_str,
        booking_id=booking_id or "",
    )
    store.track_event("booking_confirmed", uid)

    cal_note = ""
    event_id = None
    if gcal.is_configured() and date_str:
        name = pending.get("client_name") or callback.from_user.full_name or "Клиент"
        contact = store.get_client_contact_name(uid)
        svc = pending.get("service_name") or ""
        summary = f"{contact or name}" + (f" — {svc}" if svc else "")
        desc = (
            f"Telegram: {name}\n"
            f"Предложение барбера: {pending.get('suggestion_text') or ''}\n"
            f"Дата: {date_str} {time_str}"
        )
        event_id = gcal.create_event(
            summary=summary,
            date_str=date_str,
            comment=comment,
            duration_min=None,
            description=desc,
            start_time=time_str or None,  # exact HH:MM override incl. 11:20
        )
        if event_id:
            cal_note = "\n📅 В Google Calendar"
            store.update_booking(booking_id, calendar_event_id=event_id)
        else:
            cal_note = "\n⚠️ Calendar: не создалось (проверьте дату/доступ)"

    location = store.get_location()
    phone = store.get_phone()
    try:
        await callback.message.edit_text(
            (callback.message.text or "") + "\n\n✅ <b>Вы приняли это время. Ждём вас!</b>"
        )
    except Exception:
        pass
    try:
        await bot.send_message(
            uid,
            f"✅ Запись подтверждена на предложенное время.\n"
            f"📅 <b>{date_str or '—'}</b>"
            + (f" · <b>{time_str}</b>" if time_str else "")
            + f"\n📍 {location}\n"
            f"Если что-то случится: {phone}\n\n"
            f"Отменить: /cancel_booking",
        )
    except Exception:
        pass

    # notify admin group
    group = None
    try:
        import os
        group = os.getenv("ADMIN_GROUP_ID")
    except Exception:
        group = None
    if group:
        line = store.format_client_line(uid, pending.get("client_name") or callback.from_user.full_name, ref_date=date_str)
        kb = None
        if booking_id:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="❌ Отменить эту запись",
                    callback_data=f"adm:cancel:{booking_id}",
                )],
            ])
        try:
            await bot.send_message(
                group,
                f"✅ Клиент <b>принял</b> предложенное время\n"
                f"{line}\n"
                f"📅 {date_str or '—'} · {time_str or '—'}\n"
                f"💬 {pending.get('suggestion_text') or comment}"
                f"{cal_note}",
                reply_markup=kb,
            )
        except Exception as e:
            logger.error(f"suggest accept group notify: {e}")

    await callback.answer("Принято")


@router.callback_query(F.data.startswith("sug:no:"))
async def client_reject_suggestion(callback: CallbackQuery, bot: Bot):
    uid = int(callback.data.split(":")[2])
    if callback.from_user.id != uid:
        await callback.answer("Это предложение не для вас.", show_alert=True)
        return
    from src.services import settings_store as store
    pending = store.get_pending_booking(uid)
    if pending:
        store.update_pending_booking(uid, status="rejected")
    try:
        await callback.message.edit_text(
            (callback.message.text or "")
            + "\n\n❌ Вы отклонили предложение.\n"
            "Можете написать сюда удобные окна — барбер увидит. "
            "Или дождаться нового предложения."
        )
    except Exception:
        pass

    group = None
    try:
        import os
        group = os.getenv("ADMIN_GROUP_ID")
    except Exception:
        group = None
    if group:
        name = (pending or {}).get("client_name") or callback.from_user.full_name or str(uid)
        line = store.format_client_line(uid, name)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="📅 Предложить ещё раз",
                callback_data=f"adm:suggest:{uid}",
            )],
            [InlineKeyboardButton(
                text="🗑 Закрыть заявку",
                callback_data=f"adm:close_ticket:{uid}",
            )],
        ])
        try:
            await bot.send_message(
                group,
                f"❌ Клиент <b>не принял</b> предложенное время\n"
                f"{line}\n"
                f"Было: {(pending or {}).get('suggestion_text') or '—'}\n\n"
                f"Можно предложить снова или закрыть заявку.",
                reply_markup=kb,
            )
        except Exception as e:
            logger.error(f"suggest reject group notify: {e}")

    await callback.answer("Отклонено")


async def _clear_group_cancel_button(
    bot: Bot,
    b: dict,
    footer: str = "",
    skip_message_id: int | None = None,
):
    """Remove cancel button on the original group booking message (if stored)."""
    chat_id = b.get("group_chat_id")
    msg_id = b.get("group_message_id")
    if not chat_id or not msg_id:
        return
    if skip_message_id is not None and int(msg_id) == int(skip_message_id):
        return
    try:
        if footer:
            # best effort: we cannot always get old text; strip keyboard only
            await bot.edit_message_reply_markup(
                chat_id=int(chat_id),
                message_id=int(msg_id),
                reply_markup=None,
            )
        else:
            await bot.edit_message_reply_markup(
                chat_id=int(chat_id),
                message_id=int(msg_id),
                reply_markup=None,
            )
    except Exception as e:
        logger.error(f"clear group cancel btn: {e}")

@router.callback_query(F.data.startswith("adm:cancel:"))
async def admin_cancel_booking(callback: CallbackQuery, bot: Bot):
    """Barber cancels an already confirmed appointment."""
    if not await _ensure_admin_cb(callback):
        return
    booking_id = callback.data.split(":")[2]
    from src.services import settings_store as store
    existing = store.get_booking(booking_id)
    if not existing:
        await callback.answer("Запись не найдена", show_alert=True)
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        return
    if existing.get("status") != "confirmed":
        who = existing.get("status", "")
        note = "Клиент уже отменил" if "client" in who else "Уже отменено"
        await callback.answer(note, show_alert=True)
        try:
            base = callback.message.text or ""
            if "Отменено" not in base and "отменена" not in base.lower():
                await callback.message.edit_text(
                    base + f"\n\n❌ <b>{note}</b>",
                    reply_markup=None,
                )
            else:
                await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            try:
                await callback.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass
        await _clear_group_cancel_button(
            bot, existing, skip_message_id=callback.message.message_id
        )
        return
    result = store.cancel_booking(booking_id, by="barber")
    if not result.get("ok"):
        reason = result.get("reason")
        note = "Клиент уже отменил" if result.get("cancelled_by") == "client" else "Уже отменено"
        await callback.answer(note, show_alert=True)
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        return
    b = result["booking"]
    try:
        store.track_event("cancel_barber", int(b.get("user_id") or 0))
    except Exception:
        pass
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
            f"❌ Барбер отменил вашу запись на <b>{b.get('date')}</b>.\n"
            f"Можно выбрать другое время через /book.",
        )
    except Exception as e:
        logger.error(f"notify client cancel failed: {e}")
    try:
        await callback.message.edit_text(
            callback.message.text + "\n\n❌ <b>Отменено барбером</b>",
            reply_markup=None,
        )
    except Exception:
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
    # Also strip cancel button on the *other* message (confirm card vs /bookings card)
    await _clear_group_cancel_button(
        bot, b, skip_message_id=callback.message.message_id
    )
    await callback.answer("Запись отменена")


@router.callback_query(F.data.startswith("adm:setname:"))
async def admin_setname_start(callback: CallbackQuery, state: FSMContext):
    """Admin wants to save how they know this client in phone contacts."""
    if not await _ensure_admin_cb(callback):
        return
    client_id = int(callback.data.split(":")[2])
    await state.set_state(BookingStates.waiting_contact_name)
    await state.update_data(name_for_user_id=client_id)
    await callback.message.answer(
        f"📝 Как этого клиента зовут <b>в ваших контактах</b>?\n"
        f"(Telegram: будет сохранён отдельно)\n\n"
        f"Напишите имя одним сообщением.\n"
        f"/cancel — отмена"
    )
    await callback.answer()


@router.message(BookingStates.waiting_contact_name, F.text)
async def admin_setname_save(message: Message, state: FSMContext):
    if message.from_user.id not in _admin_ids():
        await state.clear()
        return
    if message.text and message.text.startswith("/cancel"):
        await state.clear()
        await message.answer("Отменено.")
        return
    data = await state.get_data()
    client_id = data.get("name_for_user_id")
    if not client_id:
        await state.clear()
        await message.answer("Сессия сброшена, попробуйте снова с кнопки.")
        return
    name = (message.text or "").strip()
    if not name:
        await message.answer("Пустое имя, попробуйте ещё раз.")
        return
    from src.services import settings_store as store
    store.save_client_contact_name(int(client_id), name)
    await state.clear()
    await message.answer(
        f"✅ Сохранено.\n"
        f"В следующих заявках будет:\n"
        f"📱 В контактах: <b>{name}</b>"
    )




@router.message(BookingStates.waiting_contact_name)
async def admin_setname_nontext(message: Message, state: FSMContext):
    """Ignore voice/photo/stickers while waiting for contact name."""
    if message.from_user and message.from_user.id not in _admin_ids():
        await state.clear()
        return
    await message.answer(
        "Нужен <b>текст</b> (имя в контактах). Голосовые и файлы не принимаются."
        + chr(10) + "/cancel — отмена"
    )


# ---------- Reminder buttons ----------

@router.callback_query(F.data.startswith("rem:yes:"))
async def rem_yes(callback: CallbackQuery):
    booking_id = callback.data.split(":")[2]
    from src.services import settings_store as store
    store.update_booking(booking_id, client_confirmed=True, client_thinking=False)
    await callback.message.edit_text(
        callback.message.text + "\n\n✅ <b>Спасибо! Ждём вас.</b>"
    )
    await callback.answer("Запись подтверждена")


@router.callback_query(F.data.startswith("rem:think:"))
async def rem_think(callback: CallbackQuery):
    booking_id = callback.data.split(":")[2]
    from src.services import settings_store as store
    store.update_booking(booking_id, client_thinking=True)
    # Morning reminder still comes
    await callback.message.edit_text(
        callback.message.text + "\n\n🤔 Хорошо, напомним ещё раз утром."
    )
    await callback.answer("Ок, напомним утром")


@router.callback_query(F.data.startswith("rem:move:"))
async def rem_move(callback: CallbackQuery, state: FSMContext, bot: Bot):
    booking_id = callback.data.split(":")[2]
    from src.services import settings_store as store
    b = store.get_booking(booking_id)
    if not b or b.get("status") != "confirmed":
        await callback.answer("Запись уже недоступна", show_alert=True)
        return
    if int(b.get("user_id", 0)) != callback.from_user.id:
        await callback.answer("Нет доступа", show_alert=True)
        return
    await state.update_data(reschedule_id=booking_id)
    await state.set_state(BookingStates.reschedule_date)
    await callback.message.edit_text(
        callback.message.text + "\n\n📅 Выберите новый день для переноса:"
    )
    await callback.message.answer(
        "Новый день:",
        reply_markup=day_selection_kb("ru"),
    )
    await callback.answer()


# ---------- Free text (questions) → group ----------

@router.message(F.text, F.chat.type == "private")
async def forward_free_text(message: Message, bot: Bot, state: FSMContext):
    # Only private client chats — never echo admin group messages
    if message.from_user and message.from_user.is_bot:
        return
    if ADMIN_GROUP_ID and str(message.chat.id) == str(ADMIN_GROUP_ID):
        return

    # Skip if we are inside booking flow
    current = await state.get_state()
    if current in (
        BookingStates.waiting_service.state,
        BookingStates.waiting_comment.state,
        BookingStates.waiting_custom_date.state,
        BookingStates.waiting_contact_name.state,
        BookingStates.admin_suggest.state,
        BookingStates.admin_edit.state,
        BookingStates.reschedule_date.state,
        BookingStates.reschedule_custom_date.state,
        BookingStates.reschedule_comment.state,
    ):
        return

    if message.text and message.text.startswith("/"):
        return

    menu_buttons = {
        "📅 Записаться", "📅 Pierakstīties",
        "📋 История записей", "📋 Pierakstu vēsture",
        "💰 Цены", "💰 Cenas",
        "📞 Связаться", "📞 Sazināties",
        "🌐 Language / Valoda",
        "❌ Отменить запись", "❌ Atcelt pierakstu",
        "отменить", "отмена", "cancel", "atcelt",
    }
    if message.text and message.text.lower() in menu_buttons:
        return

    if not ADMIN_GROUP_ID:
        return

    user = message.from_user
    try:
        from src.services import settings_store as store
        client_line = store.format_client_line(user.id, user.full_name)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💬 Написать клиенту", url=store.client_chat_url(user.id, getattr(user, "username", None)))],
            [InlineKeyboardButton(text="📝 Имя в контактах", callback_data=f"adm:setname:{user.id}")],
        ])
        await bot.send_message(
            ADMIN_GROUP_ID,
            f"💬 Сообщение\n{client_line}\n\n{message.text}",
            reply_markup=kb,
        )
    except Exception as e:
        logger.error(f"Failed to forward message: {e}")
