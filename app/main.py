from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand, MenuButtonCommands

from app import database as db
from app.core import config
from app.core.deep_link_middleware import QuestionDeepLinkMiddleware
from app.core.logging_config import setup_logging
from app.core.middlewares import AntiFloodMiddleware
from app.core.payment_middleware import PaymentIdempotencyMiddleware
from app.handlers import router
from app.services.background import create_background_tasks, stop_background_tasks

logger = logging.getLogger(__name__)


async def main() -> None:
    setup_logging()
    await db.init_db()
    await db.repair_matchmaking_state()
    logger.info("База данных и очередь успешно инициализированы")

    bot = Bot(token=config.BOT_TOKEN)

    # Стандартная синяя кнопка «Меню» Telegram и список быстрых команд.
    await bot.set_my_commands([
        BotCommand(command="start", description="🔄 Перезапустить бота"),
        BotCommand(command="support", description="🛟 Техническая поддержка"),
        BotCommand(command="news", description="📢 Канал CASPER"),
        BotCommand(command="about", description="📖 О боте"),
        BotCommand(command="privacy", description="🔐 Политика конфиденциальности"),
    ])
    await bot.set_chat_menu_button(menu_button=MenuButtonCommands())

    dispatcher = Dispatcher()
    # Capture `/start ask_...` before subscription checks so the intended
    # question target can be restored after the user confirms subscriptions.
    dispatcher.message.outer_middleware(QuestionDeepLinkMiddleware())
    # Payment idempotency must wrap payment handlers before any side effects.
    dispatcher.message.outer_middleware(PaymentIdempotencyMiddleware())
    # Middleware is attached separately to messages and callback queries.
    # This lets restricted users press the service button with block details.
    dispatcher.message.outer_middleware(AntiFloodMiddleware(slow_mode_delay=0.25))
    dispatcher.callback_query.outer_middleware(AntiFloodMiddleware(slow_mode_delay=0.25))
    dispatcher.include_router(router)

    background_tasks = create_background_tasks(bot)

    logger.info("Запуск Telegram-бота")
    try:
        # Never discard queued updates during a normal deploy/restart. In
        # particular, successful-payment updates must survive short downtime.
        await bot.delete_webhook(drop_pending_updates=False)
        await dispatcher.start_polling(bot)
    finally:
        await stop_background_tasks(background_tasks)
        await bot.session.close()
        logger.info("Бот корректно остановлен")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Остановка по запросу пользователя")
