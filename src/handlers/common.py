from pathlib import Path
import os
from datetime import datetime, timedelta

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from loguru import logger

from src.keyboards.client import main_menu_kb, language_kb, day_selection_kb

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
    waiting_comment = State()
    waiting_custom_date = State()
    waiting_contact_name = State()  # admin sets "name in contacts"
    reschedule_date = State()
    reschedule_custom_date = State()
    reschedule_comment = State()


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
    """Return date as DD/MM/YYYY"""
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
            "⌚️ Укажите удобное время\n"
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
            "⌚️ Norādiet jums ērtu laiku\n"
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
        # Always append short privacy note even to custom welcome
        caption = custom + (privacy_ru if lang == "ru" else privacy_lv)
    else:
        caption = defaults[lang]

    if WELCOME_IMAGE.exists():
        photo = FSInputFile(WELCOME_IMAGE)
        await message.answer_photo(photo=photo, caption=caption, reply_markup=main_menu_kb(lang))
    else:
        await message.answer(caption, reply_markup=main_menu_kb(lang))



async def _deny_if_closed_or_full(message_or_cb, date_str: str, lang: str, *, as_callback: bool) -> bool:
    """Return True if day is closed/full and client was notified (stop flow)."""
    from src.services import settings_store as store
    closed = store.is_blocked(date_str)
    full = (not closed) and store.is_day_full(date_str)
    if not closed and not full:
        return False
    msg = store.client_unavailable_message(date_str, lang)
    if as_callback:
        await message_or_cb.message.edit_text(msg)
        await message_or_cb.answer()
    else:
        await message_or_cb.answer(msg)
    return True

# ---------- Book ----------

@router.message(Command("book", "start_booking"))
@router.message(F.text.in_({"📅 Записаться", "📅 Pierakstīties"}))
async def cmd_book(message: Message, state: FSMContext):
    await state.clear()
    lang = get_lang(message)
    text = "Выберите день:" if lang == "ru" else "Izvēlieties dienu:"
    await message.answer(text, reply_markup=day_selection_kb(lang))


async def _apply_reschedule_day(callback: CallbackQuery, state: FSMContext, day_key: str):
    """Shared logic when client picks a new day while rescheduling."""
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
    if store.is_blocked(date_str) or store.is_day_full(date_str):
        msg = store.client_unavailable_message(date_str, lang)
        await callback.message.edit_text(msg)
        await callback.answer()
        return
    await state.update_data(reschedule_date=date_str, reschedule_day_key=day_key)
    await state.set_state(BookingStates.reschedule_comment)
    await callback.message.edit_text(
        f"Новая дата: <b>{day_label(day_key, lang)}</b> ({date_str})\n\n"
        f"Напишите время или комментарий:"
        if lang == "ru"
        else f"Jaunais datums: <b>{day_label(day_key, lang)}</b> ({date_str})\n\n"
        f"Uzrakstiet laiku vai komentāru:"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("day:"))
async def process_day(callback: CallbackQuery, state: FSMContext):
    current = await state.get_state()
    # Reschedule flow uses the same day buttons — handle here so callback is answered
    if current == BookingStates.reschedule_date.state:
        day_key = callback.data.split(":")[1]
        await _apply_reschedule_day(callback, state, day_key)
        return
    if current in (
        BookingStates.reschedule_custom_date.state,
        BookingStates.reschedule_comment.state,
    ):
        await callback.answer()
        return
    day_key = callback.data.split(":")[1]
    lang_code = (callback.from_user.language_code or "ru").lower()
    lang = "lv" if lang_code.startswith("lv") else "ru"

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
    if await _deny_if_closed_or_full(callback, date_str, lang, as_callback=True):
        return

    await state.update_data(day_key=day_key, date=date_str)
    await state.set_state(BookingStates.waiting_comment)

    name = day_label(day_key, lang)
    text_msg = (
        f"Вы выбрали: <b>{name}</b> ({date_str})\n\n"
        "Напишите желаемое время или комментарий\n"
        "(например: «после 16:00, мужская стрижка» или «около 11»)."
        if lang == "ru"
        else f"Jūs izvēlējāties: <b>{name}</b> ({date_str})\n\n"
        "Uzrakstiet vēlamo laiku vai komentāru\n"
        "(piemēram: «pēc 16:00, vīriešu griezums»)."
    )
    await callback.message.edit_text(text_msg)
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
    if await _deny_if_closed_or_full(message, date_str, lang, as_callback=False):
        return

    await state.update_data(day_key="other", date=date_str)
    await state.set_state(BookingStates.waiting_comment)

    text_msg = (
        f"Дата: <b>{date_str}</b>\n\n"
        "Напишите желаемое время или комментарий\n"
        "(например: «после 16:00, мужская стрижка»)."
        if lang == "ru"
        else f"Datums: <b>{date_str}</b>\n\n"
        "Uzrakstiet vēlamo laiku vai komentāru."
    )
    await message.answer(text_msg)


@router.message(BookingStates.waiting_comment)
async def process_comment(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    day_key = data.get("day_key", "—")
    date_str = data.get("date", "—")
    comment = message.text or "—"
    lang = get_lang(message)

    await state.clear()

    # Confirm to client
    day_name = day_label(day_key, lang)
    client_text = (
        f"✅ Заявка отправлена!\n\n"
        f"День: <b>{day_name}</b> ({date_str})\n"
        f"Комментарий: {comment}\n\n"
        f"Барбер скоро подтвердит или предложит другое время."
        if lang == "ru"
        else f"✅ Pieprasījums nosūtīts!\n\n"
        f"Diena: <b>{day_name}</b> ({date_str})\n"
        f"Komentārs: {comment}\n\n"
        f"Frizieris drīz apstiprinās vai piedāvās citu laiku."
    )
    await message.answer(client_text, reply_markup=main_menu_kb(lang))

    # Structured notification to admin group
    if ADMIN_GROUP_ID:
        user = message.from_user
        from src.services import settings_store as store
        client_line = store.format_client_line(user.id, user.full_name, ref_date=date_str)
        group_text = (
            f"🆕 <b>Новая заявка</b>\n\n"
            f"{client_line}\n"
            f"📅 День: <b>{day_label(day_key, 'ru')}</b> ({date_str})\n"
            f"💬 Комментарий: {comment}"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"adm:ok:{user.id}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"adm:no:{user.id}"),
            ],
            [
                InlineKeyboardButton(text="💬 Написать клиенту", url=f"tg://user?id={user.id}"),
            ],
            [
                InlineKeyboardButton(text="📝 Имя в контактах", callback_data=f"adm:setname:{user.id}"),
            ],
        ])
        try:
            store.save_pending_booking(
                user.id,
                date_str,
                comment,
                client_name=user.full_name or "",
                kind="book",
            )
            store.track_event("book_request", user.id)
            await bot.send_message(ADMIN_GROUP_ID, group_text, reply_markup=kb)
            logger.info(f"Booking request from {user.id} sent to group")
        except Exception as e:
            logger.error(f"Failed to send booking to group: {e}")
            await message.answer(
                "Заявка принята, но не удалось уведомить барбера. "
                "Напишите, пожалуйста, ещё раз чуть позже." if lang == "ru"
                else "Pieprasījums pieņemts, bet neizdevās paziņot frizierim."
            )


# ---------- Cancel ----------

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
    if store.is_blocked(date_str) or store.is_day_full(date_str):
        await message.answer(store.client_unavailable_message(date_str, lang))
        return
    await state.update_data(reschedule_date=date_str, reschedule_day_key="other")
    await state.set_state(BookingStates.reschedule_comment)
    await message.answer(
        f"Новая дата: <b>{date_str}</b>\n\nНапишите время или комментарий:"
    )


@router.message(BookingStates.reschedule_comment)
async def reschedule_comment(message: Message, state: FSMContext, bot: Bot):
    """Send reschedule request to admin group — same as /book (needs accept/reject)."""
    from src.services import settings_store as store
    lang = get_lang(message)
    data = await state.get_data()
    booking_id = data.get("reschedule_id")
    new_date = data.get("reschedule_date")
    comment = (message.text or "").strip() or "—"
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
    store.save_pending_booking(
        user.id,
        new_date,
        comment,
        client_name=user.full_name or "",
        kind="reschedule",
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
                    InlineKeyboardButton(text="💬 Написать клиенту", url=f"tg://user?id={user.id}"),
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
        summary = f"Barbershop: {contact or name} (перенос)"
        desc = (
            f"Telegram: {name}\n"
            f"Комментарий: {pending.get('comment', '')}\n"
            f"Дата: {pending.get('date', '')} (было {pending.get('old_date', '')})"
        )
        event_id = gcal.create_event(
            summary=summary,
            date_str=pending.get("date", ""),
            comment=pending.get("comment", ""),
            duration_min=45,
            description=desc,
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
        summary = f"Barbershop: {contact or name}"
        desc = (
            f"Telegram: {name}\n"
            f"Комментарий: {pending.get('comment', '')}\n"
            f"Дата: {pending.get('date', '')}"
        )
        event_id = gcal.create_event(
            summary=summary,
            date_str=pending.get("date", ""),
            comment=pending.get("comment", ""),
            duration_min=45,
            description=desc,
        )
        if event_id:
            cal_note = "\n📅 Добавлено в Google Calendar"
            store.update_booking(booking_id, calendar_event_id=event_id)
        elif gcal.is_configured():
            cal_note = "\n⚠️ Calendar: не удалось создать событие"

    try:
        location = store.get_location()
        if is_reschedule:
            client_msg = (
                f"✅ Перенос подтверждён!\n"
                f"Новая дата: <b>{pending.get('date')}</b>\n"
                f"💬 {pending.get('comment')}\n\n"
                f"📍 {location}\n"
                f"Если что-то случится: +371 29985759\n\n"
                f"Отменить: /cancel_booking"
            )
        else:
            client_msg = (
                f"✅ Ваша заявка подтверждена! Ждём вас.\n"
                f"📍 {location}\n"
                f"Если что-то случится, вот телефон: +371 29985759\n\n"
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
    if not await _ensure_admin_cb(callback):
        return
    client_id = int(callback.data.split(":")[2])
    from src.services import settings_store as store
    pending = store.pop_pending_booking(client_id)
    is_reschedule = bool(pending and pending.get("kind") == "reschedule")
    try:
        if is_reschedule:
            await bot.send_message(
                client_id,
                "К сожалению, перенос на это время не можем принять.\n"
                f"Старая запись на <b>{pending.get('old_date', '…')}</b> остаётся в силе.\n"
                "Можно предложить другой слот через /reschedule или /book.",
            )
            footer = "\n\n❌ <b>Перенос отклонён</b> (старая запись сохранена)"
        else:
            await bot.send_message(
                client_id,
                "К сожалению, эту заявку сейчас не можем принять. "
                "Напишите, пожалуйста, другое время через /book.",
            )
            footer = "\n\n❌ <b>Отклонено</b>"
        await callback.message.edit_text(callback.message.text + footer)
    except Exception as e:
        await callback.answer(f"Ошибка: {e}", show_alert=True)
        return
    await callback.answer("Клиент уведомлён")



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


@router.message(BookingStates.waiting_contact_name)
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
        BookingStates.waiting_comment.state,
        BookingStates.waiting_custom_date.state,
        BookingStates.waiting_contact_name.state,
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
            [InlineKeyboardButton(text="💬 Написать клиенту", url=f"tg://user?id={user.id}")],
            [InlineKeyboardButton(text="📝 Имя в контактах", callback_data=f"adm:setname:{user.id}")],
        ])
        await bot.send_message(
            ADMIN_GROUP_ID,
            f"💬 Сообщение\n{client_line}\n\n{message.text}",
            reply_markup=kb,
        )
    except Exception as e:
        logger.error(f"Failed to forward message: {e}")
