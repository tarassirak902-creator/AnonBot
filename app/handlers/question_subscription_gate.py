from __future__ import annotations

from aiogram import F
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from app import database as db
from app.core.keyboards import main_menu
from app.handlers.shared import ADMIN_IDS, router, send_brand_card
from app.services.deep_link_context import pending_question_deep_links


@router.callback_query(F.data == "check_required_subscriptions")
async def recheck_required_subscriptions_with_deep_link(callback: CallbackQuery, state: FSMContext) -> None:
    from .advertising import check_mandatory_subscriptions, mandatory_subscriptions_kb

    missing = await check_mandatory_subscriptions(callback.bot, callback.from_user.id)
    if missing:
        try:
            await callback.message.edit_reply_markup(reply_markup=mandatory_subscriptions_kb(missing))
        except TelegramBadRequest as error:
            if "message is not modified" not in str(error):
                raise
        await callback.answer("Вы ещё не подписались на все обязательные каналы.", show_alert=True)
        return

    await callback.answer("✅ Подписки подтверждены.")
    try:
        await callback.message.delete()
    except Exception:
        pass

    token = pending_question_deep_links.pop(callback.from_user.id)
    if token:
        owner = await db.get_question_owner_by_token(token)
        if owner and int(owner[4] or 0) and int(owner[0]) != callback.from_user.id:
            await db.record_question_link_visit(int(owner[0]), callback.from_user.id)
            from .questions import show_question_entry_after_start
            await state.clear()
            await show_question_entry_after_start(callback.message, token, owner)
            return

    welcome = (
        "👻 <b>Добро пожаловать в CASPER!</b>\n\n"
        "Я помогу вам найти нового собеседника, сыграть в мини-игры, "
        "посмотреть свою анкету и получить подарки.\n\n"
        "Выберите нужный раздел ниже 💜"
    )
    await send_brand_card(callback.message, "main_menu", welcome, main_menu(callback.from_user.id in ADMIN_IDS))
