import asyncio
import os
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    BotCommand,
    BotCommandScopeDefault,
    BotCommandScopeChat,
)
from dotenv import load_dotenv
from loguru import logger

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / "config" / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError(f"BOT_TOKEN is not set in {ROOT / 'config' / '.env'}")

logger.info(f"Loaded .env from {ROOT / 'config' / '.env'}")
logger.info(f"ADMIN_IDS={os.getenv('ADMIN_IDS')!r} ADMIN_GROUP_ID={os.getenv('ADMIN_GROUP_ID')!r}")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

PUBLIC_COMMANDS = [
    BotCommand(command="start", description="Главное меню / Galvenā izvēlne"),
    BotCommand(command="book", description="Записаться / Pierakstīties"),
    BotCommand(command="prices", description="Цены / Cenas"),
    BotCommand(command="history", description="История / Vēsture"),
    BotCommand(command="contact", description="Связаться / Sazināties"),
    BotCommand(command="cancel", description="Отменить / Atcelt"),
    BotCommand(command="help", description="Помощь / Palīdzība"),
]

ADMIN_EXTRA = [
    BotCommand(command="admin", description="Админ-панель"),
    BotCommand(command="settings", description="Настройки"),
    BotCommand(command="test_group", description="Тест группы"),
    BotCommand(command="block", description="Блок дня"),
    BotCommand(command="unblock", description="Снять блок дня"),
    BotCommand(command="vacation", description="Блок диапазона"),
    BotCommand(command="unvacation", description="Снять блок диапазона"),
    BotCommand(command="unblock_all", description="Снять все блоки"),
]


def get_admin_ids() -> list[int]:
    ids = []
    for x in (os.getenv("ADMIN_IDS") or "").split(","):
        x = x.strip()
        if x.isdigit():
            ids.append(int(x))
    return ids


async def set_bot_commands(bot: Bot):
    # Everyone sees only public commands
    await bot.set_my_commands(PUBLIC_COMMANDS, scope=BotCommandScopeDefault())

    # Admins additionally see admin commands in their private chat with the bot
    admin_cmds = PUBLIC_COMMANDS + ADMIN_EXTRA
    for admin_id in get_admin_ids():
        try:
            await bot.set_my_commands(
                admin_cmds,
                scope=BotCommandScopeChat(chat_id=admin_id),
            )
            logger.info(f"Admin commands set for {admin_id}")
        except Exception as e:
            logger.warning(f"Could not set admin commands for {admin_id}: {e}")

    logger.info("Bot commands registered (public + per-admin)")


def register_handlers():
    from src.handlers import admin
    from src.handlers import common
    dp.include_router(admin.router)
    dp.include_router(common.router)
    logger.info("Routers registered: admin, common")


async def on_startup():
    await set_bot_commands(bot)
    logger.info("Bot started successfully")


async def main():
    register_handlers()
    dp.startup.register(on_startup)
    logger.info("Starting bot with Long Polling...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
