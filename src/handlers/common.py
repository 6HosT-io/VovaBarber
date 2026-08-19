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


class BookingStates(StatesGroup):
    waiting_comment = State()
    waiting_custom_date = State()
    waiting_contact_name = State()  # admin sets "name in contacts"


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


# ---------- Book ----------

@router.message(Command("book", "start_booking"))
@router.message(F.text.in_({"📅 Записаться", "📅 Pierakstīties"}))
async def cmd_book(message: Message, state: FSMContext):
    await state.clear()
    lang = get_lang(message)
    text = "Выберите день:" if lang == "ru" else "Izvēlieties dienu:"
    await message.answer(text, reply_markup=day_selection_kb(lang))


@router.callback_query(F.data.startswith("day:"))
async def process_day(callback: CallbackQuery, state: FSMContext):
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
    from src.services import settings_store as store
    if store.is_blocked(date_str):
        msg = (
            f"Этот день (<b>{date_str}</b>) недоступен для записи. Выберите другой."
            if lang == "ru"
            else f"Šī diena (<b>{date_str}</b>) nav pieejama. Izvēlieties citu."
        )
        await callback.message.edit_text(msg)
        await callback.answer()
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
    from src.services import settings_store as store
    if store.is_blocked(date_str):
        msg = (
            f"Этот день (<b>{date_str}</b>) недоступен для записи. Выберите другой."
            if lang == "ru"
            else f"Šī diena (<b>{date_str}</b>) nav pieejama. Izvēlieties citu."
        )
        await message.answer(msg)
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
        client_line = store.format_client_line(user.id, user.full_name)
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
            )
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
        "Хорошо, текущая запись/действие отменено.\n"
        "Если нужно записаться заново — нажмите «Записаться» или /book."
        if lang == "ru"
        else "Labi, pašreizējā darbība atcelta.\n"
        "Ja vajag pierakstīties no jauna — nospiediet «Pierakstīties» vai /book."
    )
    await message.answer(text, reply_markup=main_menu_kb(lang))

    # Notify group
    if ADMIN_GROUP_ID:
        user = message.from_user
        try:
            from src.services import settings_store as store
            client_line = store.format_client_line(user.id, user.full_name)
            await bot.send_message(
                ADMIN_GROUP_ID,
                f"❌ Отмена\n{client_line}",
            )
        except Exception as e:
            logger.error(f"Failed to notify cancel: {e}")


# ---------- Prices / History / Contact / Help ----------

@router.message(Command("prices", "price"))
@router.message(F.text.in_({"💰 Цены", "💰 Cenas"}))
async def cmd_prices(message: Message):
    from src.services import settings_store as store
    lang = get_lang(message)
    body = store.format_services_text(lang)
    header = "💰 <b>Цены</b>\n\n" if lang == "ru" else "💰 <b>Cenas</b>\n\n"
    await message.answer(header + body)


@router.message(Command("history"))
@router.message(F.text.in_({"📋 История записей", "📋 Pierakstu vēsture"}))
async def cmd_history(message: Message):
    from src.services import settings_store as store
    lang = get_lang(message)
    items = store.get_last_services(message.from_user.id, limit=8)
    if not items:
        text = (
            "📋 Пока история пуста.\nКогда появятся подтверждённые записи, они будут здесь."
            if lang == "ru"
            else "📋 Vēsture pagaidām tukša."
        )
        await message.answer(text)
        return
    lines = []
    for e in items:
        svc = e.get("service", "—")
        dt = e.get("date", "")
        lines.append(f"• {dt + ' — ' if dt else ''}{svc}")
    header = "📋 Ваша история:\n\n" if lang == "ru" else "📋 Jūsu vēsture:\n\n"
    await message.answer(header + "\n".join(lines))


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
    client_id = int(callback.data.split(":")[2])
    from src.services import settings_store as store
    from src.services import calendar as gcal

    pending = store.pop_pending_booking(client_id)
    cal_note = ""
    if pending:
        # Record service for "Last time used services"
        store.add_service_history(
            client_id,
            pending.get("comment") or "услуга",
            pending.get("date") or "",
        )
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
        elif gcal.is_configured():
            cal_note = "\n⚠️ Calendar: не удалось создать событие"
        # if not configured — silent, no note

    try:
        location = store.get_location()
        await bot.send_message(
            client_id,
            f"✅ Ваша заявка подтверждена! Ждём вас.\n"
            f"📍 {location}\n"
            f"Если что-то случится, вот телефон: +371 29985759",
        )
        await callback.message.edit_text(
            callback.message.text + f"\n\n✅ <b>Подтверждено</b>{cal_note}"
        )
    except Exception as e:
        await callback.answer(f"Не удалось написать клиенту: {e}", show_alert=True)
        return
    await callback.answer("Клиент уведомлён")


@router.callback_query(F.data.startswith("adm:no:"))
async def admin_reject(callback: CallbackQuery, bot: Bot):
    client_id = int(callback.data.split(":")[2])
    try:
        await bot.send_message(
            client_id,
            "К сожалению, эту заявку сейчас не можем принять. "
            "Напишите, пожалуйста, другое время через /book."
        )
        await callback.message.edit_text(callback.message.text + "\n\n❌ <b>Отклонено</b>")
    except Exception as e:
        await callback.answer(f"Ошибка: {e}", show_alert=True)
        return
    await callback.answer("Клиент уведомлён")


@router.callback_query(F.data.startswith("adm:setname:"))
async def admin_setname_start(callback: CallbackQuery, state: FSMContext):
    """Admin wants to save how they know this client in phone contacts."""
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


# ---------- Free text (questions) → group ----------

@router.message(F.text)
async def forward_free_text(message: Message, bot: Bot, state: FSMContext):
    # Skip if we are inside booking flow
    current = await state.get_state()
    if current in (
        BookingStates.waiting_comment.state,
        BookingStates.waiting_custom_date.state,
        BookingStates.waiting_contact_name.state,
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
