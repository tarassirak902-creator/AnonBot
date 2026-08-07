from .shared import *


def _achievement_lines(active_count: int) -> tuple[str, str]:
    levels = [
        (1, "🥉 Первое приглашение"),
        (5, "🥈 5 активных друзей"),
        (25, "🥇 25 активных друзей"),
        (100, "💎 100 активных друзей"),
    ]
    unlocked = [title for threshold, title in levels if active_count >= threshold]
    next_level = next(((threshold, title) for threshold, title in levels if active_count < threshold), None)
    unlocked_text = "\n".join(f"✅ {title}" for title in unlocked) if unlocked else "Пока нет открытых достижений"
    if next_level:
        left = next_level[0] - active_count
        next_text = f"До достижения «{next_level[1]}» осталось: <b>{left}</b>"
    else:
        next_text = "Открыты все реферальные достижения! 👑"
    return unlocked_text, next_text


async def _referral_screen(bot, user_id: int, *, parent: str = "invite") -> tuple[str, InlineKeyboardMarkup]:
    _ref_link, share_url, stats = await prepare_referral_data(bot, user_id)
    unlocked, next_text = _achievement_lines(stats["active"])
    text = (
        "📊 <b>Статистика приглашений</b>\n\n"
        f"👤 Всего приглашено: <b>{stats['total']}</b>\n"
        f"✅ Активных друзей: <b>{stats['active']}</b>\n"
        f"⏳ Ещё набирают активность: <b>{stats['pending']}</b>\n"
        f"🎁 Получено наград: <b>{stats['rewards']}</b>\n"
        f"⭐ Начислено на баланс: <b>{stats['reward_stars']}</b>\n\n"
        "🏅 <b>Достижения:</b>\n"
        f"{unlocked}\n\n"
        f"{next_text}\n\n"
        "Друг считается активным после <b>5 завершённых диалогов</b>."
    )
    if parent == "growth":
        back_callback, back_label = "platform_referrals", "⬅️ Приглашения"
    else:
        back_callback, back_label = "referral_back_to_invite", "⬅️ Приглашение"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=back_label, callback_data=back_callback)],
    ])
    return text, kb


@router.callback_query(F.data.in_({"referral_stats", "referral_stats_growth"}))
async def referral_stats(callback: CallbackQuery):
    await callback.answer()
    parent = "growth" if callback.data == "referral_stats_growth" else "invite"
    text, kb = await _referral_screen(callback.bot, callback.from_user.id, parent=parent)
    await safe_delete_message(callback.message)
    await send_brand_card(callback.message, "invite", text, kb)


@router.callback_query(F.data == "referral_back_to_invite")
async def referral_back_to_invite(callback: CallbackQuery):
    await callback.answer()
    await safe_delete_message(callback.message)
    _ref_link, share_url, stats = await prepare_referral_data(
        callback.bot,
        callback.from_user.id,
        compact_invitation=True,
    )
    text = (
        "👥 <b>Пригласить друга</b>\n\n"
        "Отправьте необычное приглашение человеку из своих диалогов Telegram.\n\n"
        "🎁 После 5 завершённых диалогов приглашённого друга вы получите "
        "<b>50 виртуальных ⭐</b>.\n\n"
        f"👤 Приглашено: <b>{stats['total']}</b>\n"
        f"✅ Активных: <b>{stats['active']}</b>\n"
        f"⭐ Получено: <b>{stats['reward_stars']}</b>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📨 Пригласить друга", url=share_url)],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="referral_stats")],
        [InlineKeyboardButton(text="⬅️ Главное меню", callback_data="nav_main_menu")],
    ])
    await send_brand_card(callback.message, "invite", text, kb)
