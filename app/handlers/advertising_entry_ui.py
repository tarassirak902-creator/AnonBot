from __future__ import annotations

from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from app.core.config import BOT_USERNAME

from .shared import router


async def _delete_current(message) -> None:
    try:
        await message.delete()
    except Exception:
        pass


def _back(callback_data: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="◀️ Назад", callback_data=callback_data)
    ]])


async def _runtime_bot_username(callback: CallbackQuery) -> str:
    try:
        info = await callback.bot.get_me()
        username = (info.username or "").strip().lstrip("@")
    except Exception:
        username = (BOT_USERNAME or "").strip().lstrip("@")
    return username


@router.callback_query(F.data == "ads_buy_post")
async def ads_buy_post_entry(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state("AdOrder:waiting_post")
    await _delete_current(callback.message)
    await callback.message.answer(
        "Перешлите или отправьте рекламный пост, который хотите, чтобы CASPER показывал пользователям.",
        reply_markup=_back("ads_back_menu"),
    )
    await callback.answer()


@router.callback_query(F.data == "ads_back_post")
async def ads_back_post_entry(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state("AdOrder:waiting_post")
    await _delete_current(callback.message)
    await callback.message.answer(
        "Перешлите или отправьте рекламный пост, который хотите, чтобы CASPER показывал пользователям.",
        reply_markup=_back("ads_back_menu"),
    )
    await callback.answer()


@router.callback_query(F.data.in_({"ads_community_channel", "ads_community_group"}))
async def ads_choose_community_type_entry(callback: CallbackQuery, state: FSMContext) -> None:
    community_type = "channel" if (callback.data or "").endswith("channel") else "group"
    await state.update_data(community_type=community_type)
    await state.set_state("AdOrder:waiting_channel")
    await _delete_current(callback.message)

    username = await _runtime_bot_username(callback)
    bot_label = f"@{username}" if username else "текущего бота CASPER"
    await callback.message.answer(
        "Для запуска рекламы выполните два действия:\n"
        f"1. Добавьте {bot_label} администратором в ваш канал или группу;\n"
        "2. Отправьте @username или публичную ссылку на это сообщество.",
        reply_markup=_back("ads_back_community_type"),
    )
    await callback.answer()
