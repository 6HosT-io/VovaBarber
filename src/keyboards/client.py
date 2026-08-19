from aiogram.types import ReplyKeyboardMarkup, InlineKeyboardMarkup
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder


def main_menu_kb(lang: str = "ru") -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    if lang == "ru":
        builder.button(text="📅 Записаться")
        builder.button(text="📋 История записей")
        builder.button(text="💰 Цены")
        builder.button(text="📞 Связаться")
        builder.button(text="🌐 Language / Valoda")
    else:
        builder.button(text="📅 Pierakstīties")
        builder.button(text="📋 Pierakstu vēsture")
        builder.button(text="💰 Cenas")
        builder.button(text="📞 Sazināties")
        builder.button(text="🌐 Language / Valoda")
    builder.adjust(2, 2, 1)
    return builder.as_markup(resize_keyboard=True)


def language_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🇷🇺 Русский", callback_data="lang:ru")
    builder.button(text="🇱🇻 Latviešu", callback_data="lang:lv")
    builder.adjust(2)
    return builder.as_markup()


def day_selection_kb(lang: str = "ru") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if lang == "ru":
        builder.button(text="Сегодня", callback_data="day:today")
        builder.button(text="Завтра", callback_data="day:tomorrow")
        builder.button(text="Послезавтра", callback_data="day:day_after")
        builder.button(text="Другая дата", callback_data="day:other")
    else:
        builder.button(text="Šodien", callback_data="day:today")
        builder.button(text="Rīt", callback_data="day:tomorrow")
        builder.button(text="Parīt", callback_data="day:day_after")
        builder.button(text="Cita datums", callback_data="day:other")
    builder.adjust(1)
    return builder.as_markup()
