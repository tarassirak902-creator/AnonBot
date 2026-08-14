from .shared import *
from pathlib import Path
import html
from app.core.config import BASE_DIR
from .admin_users import admin_users_menu_kb


def _admin_name(user) -> str:
    """Красивое имя администратора для записи в лог-канале."""
    full_name = " ".join(
        part for part in (getattr(user, "first_name", None), getattr(user, "last_name", None))
        if part
    ).strip()
    username = getattr(user, "username", None)

    if full_name and username:
        return f"{full_name} (@{username})"
    if full_name:
        return full_name
    if username:
        return f"@{username}"
    return "Администратор"


async def _edit_log_message_with_result( callback: types.CallbackQuery, action_text: str, ) -> bool:
    """ Редактирует исходное сообщение в лог-канале: убирает кнопки и добавляет сведения об администраторе. Возвращает False, если сообщение уже было обработано. """
    message = callback.message
    marker = "✅ <b>Обработано администратором</b>"

    current_text = message.html_text or message.text or ""
    current_caption = html.escape(message.caption or "")

    if marker in current_text or marker in current_caption:
        await callback.answer(
            "Эта запись уже обработана другим администратором.",
            show_alert=True,
        )
        return False

    admin = callback.from_user
    footer = (
        "\n\n"
        "━━━━━━━━━━━━━━\n"
        f"{marker}\n"
        f"👤 Администратор: <b>{html.escape(_admin_name(admin))}</b>\n"
        f"🆔 ID администратора: <code>{admin.id}</code>\n"
        f"⚙️ Действие: <b>{html.escape(action_text)}</b>"
    )

    try:
        if message.text is not None:
            await message.edit_text(
                current_text + footer,
                parse_mode="HTML",
                reply_markup=None,
            )
        elif message.caption is not None:
            await message.edit_caption(
                caption=current_caption + footer,
                parse_mode="HTML",
                reply_markup=None,
            )
        else:
            await message.edit_reply_markup(reply_markup=None)
        return True
    except Exception:
        # Даже если текст изменить нельзя, по возможности убираем кнопки.
        try:
            await message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        return True


def _restriction_removed_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="▶️ Старт",
                    callback_data="restriction_removed_start",
                )
            ]
        ]
    )


async def _send_restriction_notice(
    bot,
    user_id: int,
    *,
    permanent: bool,
) -> None:
    """Отправляет пользователю уведомление об ограничении с кнопкой деталей."""
    button_text = "🚫 ВЫ ЗАБЛОКИРОВАНЫ" if permanent else "⌛ ВАМ ЗАПРЕЩЕНО ПИСАТЬ СУТКИ"
    notice_text = (
        "⛔ <b>Ваш аккаунт заблокирован администратором "
        "за нарушение правил.</b>"
        if permanent
        else "🔇 <b>Ваш аккаунт временно ограничен на 24 часа администрацией.</b>"
    )
    details_kb = InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(
                text=button_text,
                callback_data="is_banned_alert",
            )
        ]]
    )
    await bot.send_message(
        user_id,
        notice_text,
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove(),
    )
    await bot.send_message(
        user_id,
        "Нажмите на кнопку ниже, чтобы посмотреть срок ограничения:",
        reply_markup=details_kb,
    )


async def _claim_log_action(callback: types.CallbackQuery, action: str) -> bool:
    key = f"log:{callback.message.chat.id}:{callback.message.message_id}"
    claimed = await db.claim_admin_action(key, callback.from_user.id, action)
    if not claimed:
        await callback.answer("Эта запись уже обработана другим администратором.", show_alert=True)
    return claimed


async def _log_admin_restriction(bot, admin, target_id: int, action: str) -> None:
    user = await db.get_user(target_id)
    username = f"@{user[1]}" if user and user[1] else "нет"
    full_name = " ".join(
        x for x in ((user[2] if user else None), (user[3] if user else None)) if x
    ).strip() or "не указано"
    try:
        await bot.send_message(
            LOG_CHANNEL_ID,
            "🛡 <b>Ограничение выдано из админ-панели</b>\n\n"
            f"👤 Администратор: <b>{html.escape(_admin_name(admin))}</b>\n"
            f"🆔 ID администратора: <code>{admin.id}</code>\n"
            f"🎯 Пользователь: <b>{html.escape(full_name)}</b> ({html.escape(username)})\n"
            f"🆔 ID пользователя: <code>{target_id}</code>\n"
            f"⚙️ Ограничение: <b>{html.escape(action)}</b>",
            parse_mode="HTML",
        )
    except Exception:
        logger.exception(
            "Не удалось отправить запись об ограничении в лог-канал: "
            "admin_id=%s, target_id=%s, action=%s",
            admin.id,
            target_id,
            action,
        )


async def _notify_restriction_removed(bot, user_id: int) -> None:
    """Уведомляет пользователя о снятии ограничения."""
    try:
        await bot.send_message(
            user_id,
            (
                "✅ <b>Ограничение с вашего аккаунта снято.</b>\n\n"
                "Вы снова можете пользоваться ботом и искать собеседника.\n"
                "Пожалуйста, соблюдайте правила, чтобы не получить новое ограничение."
            ),
            parse_mode="HTML",
            reply_markup=_restriction_removed_kb(),
        )
    except Exception:
        logger.exception(
            "Не удалось уведомить пользователя о снятии ограничения: "
            "user_id=%s",
            user_id,
        )



async def _cleanup_user_session_before_restriction(
    bot,
    user_id: int,
) -> None:
    cancel_search_timer(user_id)
    cancel_unread_reminder(user_id)
    await delete_search_card(bot, user_id)
    await db.remove_from_queue(user_id)

    partner_id = await db.end_chat(user_id)
    if not partner_id:
        return

    cancel_inactivity_timer(user_id, partner_id)
    cancel_unread_reminder(partner_id)

    try:
        await bot.send_message(
            partner_id,
            (
                "👻 <b>CASPER</b>\n\n"
                "Собеседник был отключён модератором. "
                "Диалог завершён."
            ),
            parse_mode="HTML",
            reply_markup=main_menu(partner_id in ADMIN_IDS),
        )
    except Exception:
        logger.exception(
            "Не удалось уведомить собеседника об отключении модератором: "
            "user_id=%s, partner_id=%s",
            user_id,
            partner_id,
        )


@router.callback_query(F.data == "restriction_removed_start")
async def restriction_removed_start( callback: types.CallbackQuery, state: FSMContext, ):
    """ Возвращает пользователя в главное меню после снятия ограничения. Это повторяет основной пользовательский результат /start: очищает состояние и показывает главное меню. """
    await state.clear()
    await callback.answer()

    try:
        await callback.message.delete()
    except Exception:
        pass

    await show_main_menu_screen(
        callback.message,
        callback.from_user.id,
    )


@router.callback_query(F.data == "admin_user_search")
async def start_user_search(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        return
    await callback.answer()
    text = "🔍 Введите Telegram ID или username пользователя для поиска:"
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="↩️ Назад", callback_data="admin_back_to_users")]
        ]
    )
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)
    await state.set_state(UserSearch.waiting_for_query)


@router.callback_query(F.data == "admin_warned_list")
async def show_warned_users_list(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    await callback.answer()

    async with aiosqlite.connect(db.DB_PATH) as connection:
        cursor = await connection.execute(
            "SELECT user_id, username, first_name, last_name, warnings "
            "FROM users WHERE warnings > 0 "
            "ORDER BY warnings DESC LIMIT 50"
        )
        rows = await cursor.fetchall()

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="↩️ Назад", callback_data="admin_back_to_users")]
        ]
    )

    if not rows:
        text = "🎉 <b>Нет пользователей с предупреждениями.</b>"
    else:
        text = "📋 <b>Список пользователей с предупреждениями:</b>\n\n"
        for idx, row in enumerate(rows, 1):
            uid, username, first_name, last_name, warnings = row
            text += (
                f"<b>{idx}. {html.escape(first_name or '')}</b> "
                f"(@{html.escape(username or 'нет')})\n"
                f"├ ID: <code>{uid}</code>\n"
                f"└ 🚨 Варнов: <b>{warnings}</b>\n\n"
            )

    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data == "admin_restricted_list")
async def show_restricted_users_list(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    await callback.answer()

    async with aiosqlite.connect(db.DB_PATH) as connection:
        cursor = await connection.execute(
            "SELECT user_id, username, first_name, last_name, blocked_until "
            "FROM users WHERE blocked=1 "
            "ORDER BY CASE WHEN blocked_until IS NULL THEN 0 ELSE 1 END, blocked_until DESC LIMIT 50"
        )
        rows = await cursor.fetchall()

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="↩️ Назад", callback_data="admin_back_to_users")]
    ])
    if not rows:
        text = "✅ <b>Нет пользователей с ограничениями.</b>"
    else:
        text = "🔒 <b>Ограниченные пользователи:</b>\n\n"
        for idx, (uid, username, first_name, last_name, blocked_until) in enumerate(rows, 1):
            name = " ".join(part for part in (first_name, last_name) if part).strip() or "Без имени"
            username_text = f"@{html.escape(username)}" if username else "нет username"
            if blocked_until:
                try:
                    until_text = datetime.fromisoformat(blocked_until).strftime("%d.%m.%Y %H:%M")
                except Exception:
                    until_text = html.escape(str(blocked_until))
                restriction = f"до <b>{until_text}</b>"
            else:
                restriction = "<b>бессрочно</b>"
            text += (
                f"<b>{idx}. {html.escape(name)}</b> ({username_text})\n"
                f"├ ID: <code>{uid}</code>\n"
                f"└ Ограничение: {restriction}\n\n"
            )

    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data == "admin_back_to_users")
async def back_to_users_menu(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        return
    await state.clear()
    await callback.answer()
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer(
        "📊 <b>Статистика и пользователи</b>",
        parse_mode="HTML",
        reply_markup=admin_users_menu_kb(),
    )


@router.callback_query(F.data == "admin_back_to_panel")
async def back_to_admin_panel_callback( callback: types.CallbackQuery, state: FSMContext, ):
    if callback.from_user.id not in ADMIN_IDS:
        return
    await state.clear()
    await callback.answer()
    await safe_delete_message(callback.message)
    await send_brand_card(
        callback.message,
        "admin",
        "⚙️ <b>Панель управления CASPER</b>\n\nУправление пользователями, рекламой, статистикой и настройками бота.",
        admin_panel(),
    )


@router.callback_query(F.data.startswith("toggle_block_"))
async def toggle_block(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return

    uid = int(callback.data.split("_")[2])
    user = await db.get_user(uid)
    if not user:
        await callback.answer("Пользователь не найден", show_alert=True)
        return

    new_state = not bool(user[5])
    await db.block_user(uid, new_state)

    if not new_state:
        await _notify_restriction_removed(callback.bot, uid)

    await _admin_audit(
        callback.from_user.id,
        uid,
        "block" if new_state else "unblock",
        "source=admin_card",
    )
    await _log_admin_restriction(callback.bot, callback.from_user, uid, "Бессрочная блокировка" if new_state else "Ограничение снято")
    await callback.answer(
        f"Пользователь {'заблокирован' if new_state else 'разблокирован'}.",
        show_alert=True,
    )
    await refresh_admin_user_message(
        callback.message,
        uid,
        "✅ Действие выполнено",
    )


@router.callback_query(F.data.startswith("warn_"))
async def warn_user(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return

    target_id = int(callback.data.split("_")[1])
    warns_count, auto_banned = await db.warn_user(target_id)
    await _admin_audit(
        callback.from_user.id,
        target_id,
        "warn",
        f"count={warns_count}; source=admin_card",
    )

    try:
        if auto_banned:
            await callback.bot.send_message(
                target_id,
                "⛔ Вы получили третье предупреждение и автоматически заблокированы бессрочно.",
            )
        else:
            await callback.bot.send_message(
                target_id,
                f"⚠️ Вам выдано предупреждение #{warns_count} из 3!",
            )
    except Exception:
        logger.exception(
            "Не удалось уведомить пользователя о предупреждении: "
            "target_id=%s, warnings=%s, auto_banned=%s",
            target_id,
            warns_count,
            auto_banned,
        )

    if auto_banned:
        await callback.answer(
            "⛔ Третье предупреждение: пользователь автоматически заблокирован!",
            show_alert=True,
        )
        prefix = (
            "⛔ Выдано третье предупреждение — "
            "пользователь автоматически заблокирован"
        )
    else:
        await callback.answer(
            f"✅ Предупреждение #{warns_count} из 3 выдано!",
            show_alert=True,
        )
        prefix = f"✅ Выдано предупреждение #{warns_count} из 3"

    await refresh_admin_user_message(callback.message, target_id, prefix)


@router.callback_query(F.data.startswith("admin_user_card_"))
async def refresh_user_card_callback(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    uid = int(callback.data.rsplit("_", 1)[1])
    await callback.answer()
    await refresh_admin_user_message(callback.message, uid)


@router.callback_query(F.data == "admin_logs_view")
async def admin_logs_view(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    await callback.answer()

    log_path = Path(BASE_DIR) / "logs" / "bot.log"
    if not log_path.exists():
        text = "Лог-файл пока отсутствует."
    else:
        lines = log_path.read_text(
            encoding="utf-8",
            errors="replace",
        ).splitlines()[-30:]
        content = "\n".join(lines) or "Лог пуст."
        text = (
            "📋 <b>Последние записи:</b>\n\n"
            "<pre>"
            + html.escape(content[-3500:])
            + "</pre>"
        )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔄 Обновить",
                    callback_data="admin_logs_view",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📥 Скачать .txt",
                    callback_data="admin_logs_download",
                )
            ],
            [
                InlineKeyboardButton(
                    text="↩️ Назад",
                    callback_data="admin_logs_menu",
                )
            ],
        ]
    )
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=kb,
    )


@router.callback_query(F.data == "admin_logs_download")
async def admin_logs_download(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    await callback.answer()

    log_path = Path(BASE_DIR) / "logs" / "bot.log"
    data = log_path.read_bytes() if log_path.exists() else b"Log is empty.\n"
    await callback.message.answer_document(
        BufferedInputFile(data, filename="bot_log.txt"),
        caption="📥 Полный лог бота",
    )


@router.callback_query(F.data == "admin_logs_menu")
async def admin_logs_menu(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    await callback.answer()

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="👁 Все записи",
                    callback_data="admin_logs_view",
                )
            ],
            [
                InlineKeyboardButton(
                    text="⚠️ Ошибки",
                    callback_data="admin_logs_filter_errors",
                ),
                InlineKeyboardButton(
                    text="🛡 Админы",
                    callback_data="admin_logs_filter_admins",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="💰 Платежи",
                    callback_data="admin_logs_filter_payments",
                ),
                InlineKeyboardButton(
                    text="🚨 Жалобы",
                    callback_data="admin_logs_filter_complaints",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📥 Скачать лог .txt",
                    callback_data="admin_logs_download",
                )
            ],
            [
                InlineKeyboardButton(
                    text="↩️ Назад",
                    callback_data="admin_back_to_panel",
                )
            ],
        ]
    )

    try:
        await callback.message.delete()
    except Exception:
        pass

    await callback.message.answer(
        "📋 <b>Логи бота</b>\n\nВыберите действие:",
        parse_mode="HTML",
        reply_markup=kb,
    )


@router.callback_query(F.data == "is_banned_alert")
async def show_block_details(callback: types.CallbackQuery):
    is_blocked, blocked_until = await db.get_user_block_status(
        callback.from_user.id
    )

    if not is_blocked:
        await callback.answer(
            "✅ Ограничение уже снято. Нажмите «Старт», чтобы продолжить.",
            show_alert=True,
        )
        return

    if blocked_until is None:
        text = (
            "⛔ Ваш аккаунт заблокирован бессрочно. "
            "Для разблокировки обратитесь к администрации."
        )
    else:
        remaining = blocked_until - datetime.now()
        total_minutes = max(1, int(remaining.total_seconds() // 60))
        hours, minutes = divmod(total_minutes, 60)
        remaining_text = (
            f"{hours} ч. {minutes} мин." if hours else f"{minutes} мин."
        )
        text = (
            "🔇 Вам временно запрещено пользоваться ботом.\n"
            f"Осталось примерно: {remaining_text}\n"
            f"Ограничение действует до: {blocked_until:%d.%m.%Y %H:%M}."
        )

    await callback.answer(text, show_alert=True)


@router.callback_query(F.data.startswith("log_warn_"))
async def log_warn_user(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(
            "⛔ Только для администраторов!",
            show_alert=True,
        )
        return

    # Сначала блокируем повторное нажатие по уже обработанной записи.
    existing_text = callback.message.html_text or callback.message.text or ""
    existing_caption = (
        html.escape(callback.message.caption or "")
    )
    if "✅ <b>Обработано администратором</b>" in (
        existing_text + existing_caption
    ):
        await callback.answer(
            "Эта запись уже обработана.",
            show_alert=True,
        )
        return

    target_id = int(callback.data.split("_")[2])
    if not await _claim_log_action(callback, "warn"):
        return
    warns_count, auto_banned = await db.warn_user(target_id)
    await _admin_audit(
        callback.from_user.id,
        target_id,
        "warn",
        f"count={warns_count}; source=log",
    )

    try:
        if auto_banned:
            await callback.bot.send_message(
                target_id,
                "⛔ Вы получили третье предупреждение и автоматически заблокированы бессрочно.",
            )
        else:
            await callback.bot.send_message(
                target_id,
                f"⚠️ Вам выдано предупреждение от администрации "
                f"#{warns_count} из 3!",
            )
    except Exception:
        logger.exception(
            "Не удалось уведомить пользователя о предупреждении: "
            "target_id=%s, warnings=%s, auto_banned=%s",
            target_id,
            warns_count,
            auto_banned,
        )

    action = (
        "Третье предупреждение и автоматическая бессрочная блокировка"
        if auto_banned
        else f"Предупреждение #{warns_count} из 3"
    )
    await _edit_log_message_with_result(callback, action)

    alert = (
        "⛔ Третье предупреждение: пользователь автоматически заблокирован!"
        if auto_banned
        else f"✅ Предупреждение #{warns_count} из 3 выдано!"
    )
    await callback.answer(alert, show_alert=True)


@router.callback_query(F.data.startswith("log_mute_"))
async def log_mute_user(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(
            "⛔ Только для администраторов!",
            show_alert=True,
        )
        return

    existing_text = callback.message.html_text or callback.message.text or ""
    existing_caption = (
        html.escape(callback.message.caption or "")
    )
    if "✅ <b>Обработано администратором</b>" in (
        existing_text + existing_caption
    ):
        await callback.answer(
            "Эта запись уже обработана.",
            show_alert=True,
        )
        return

    target_id = int(callback.data.split("_")[2])
    if not await _claim_log_action(callback, "mute"):
        return
    partner_id = await db.end_chat(target_id)

    if partner_id:
        cancel_inactivity_timer(target_id, partner_id)
        cancel_unread_reminder(target_id)
        cancel_unread_reminder(partner_id)
        try:
            await callback.bot.send_message(
                partner_id,
                (
                    "⛔ Диалог завершён. Ваш собеседник ограничен "
                    "за нарушение правил."
                ),
                reply_markup=main_menu(partner_id in ADMIN_IDS),
            )
            await callback.bot.send_message(
                partner_id,
                "Хотите узнать, с кем вы общались?",
                reply_markup=reveal_offer_kb(target_id),
            )
        except Exception:
            pass

    await db.block_user(
        target_id,
        True,
        datetime.now() + timedelta(hours=24),
    )
    await _admin_audit(
        callback.from_user.id,
        target_id,
        "mute",
        "24h; source=log",
    )

    try:
        blocked_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="⌛ ВАМ ЗАПРЕЩЕНО ПИСАТЬ СУТКИ",
                        callback_data="is_banned_alert",
                    )
                ]
            ]
        )
        await callback.bot.send_message(
            target_id,
            (
                "🔇 <b>Ваш аккаунт временно ограничен "
                "на 24 часа администрацией.</b>"
            ),
            parse_mode="HTML",
            reply_markup=ReplyKeyboardRemove(),
        )
        await callback.bot.send_message(
            target_id,
            "Нажмите на кнопку ниже для подробностей:",
            reply_markup=blocked_kb,
        )
    except Exception:
        pass

    await _edit_log_message_with_result(
        callback,
        "Временное ограничение на 24 часа",
    )
    await callback.answer(
        "✅ Пользователь ограничен администратором!",
        show_alert=True,
    )


@router.callback_query(F.data.startswith("log_ban_"))
async def log_ban_user(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(
            "⛔ Только для администраторов!",
            show_alert=True,
        )
        return

    existing_text = callback.message.html_text or callback.message.text or ""
    existing_caption = (
        html.escape(callback.message.caption or "")
    )
    if "✅ <b>Обработано администратором</b>" in (
        existing_text + existing_caption
    ):
        await callback.answer(
            "Эта запись уже обработана.",
            show_alert=True,
        )
        return

    target_id = int(callback.data.split("_")[2])
    if not await _claim_log_action(callback, "ban"):
        return
    partner_id = await db.end_chat(target_id)

    if partner_id:
        cancel_inactivity_timer(target_id, partner_id)
        cancel_unread_reminder(target_id)
        cancel_unread_reminder(partner_id)
        try:
            await callback.bot.send_message(
                partner_id,
                (
                    "⛔ Диалог завершён. Ваш собеседник заблокирован "
                    "за нарушение правил."
                ),
                reply_markup=main_menu(partner_id in ADMIN_IDS),
            )
            await callback.bot.send_message(
                partner_id,
                "Хотите узнать, с кем вы общались?",
                reply_markup=reveal_offer_kb(target_id),
            )
        except Exception:
            pass

    await db.block_user(target_id, True)
    await _admin_audit(
        callback.from_user.id,
        target_id,
        "ban",
        "permanent; source=log",
    )

    try:
        blocked_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🚫 ВЫ ЗАБЛОКИРОВАНЫ",
                        callback_data="is_banned_alert",
                    )
                ]
            ]
        )
        await callback.bot.send_message(
            target_id,
            (
                "⛔ <b>Ваш аккаунт заблокирован администратором "
                "за нарушение правил.</b>"
            ),
            parse_mode="HTML",
            reply_markup=ReplyKeyboardRemove(),
        )
        await callback.bot.send_message(
            target_id,
            "Нажмите на кнопку ниже для подробностей:",
            reply_markup=blocked_kb,
        )
    except Exception:
        pass

    await _edit_log_message_with_result(
        callback,
        "Бессрочная блокировка",
    )
    await callback.answer(
        "✅ Пользователь забанен навсегда!",
        show_alert=True,
    )


async def _admin_audit( admin_id: int, target_id: int, action: str, details: str = "", ):
    await db.log_action(
        target_id,
        f"admin:{action}",
        f"admin_id={admin_id}; {details}".strip(),
    )


@router.callback_query(F.data.startswith("admin_confirm_vip_"))
async def confirm_vip(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return

    uid = int(callback.data.rsplit("_", 1)[1])
    await callback.answer()
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Выдать VIP",
                    callback_data=f"admin_give_vip_{uid}",
                ),
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data=f"admin_user_card_{uid}",
                ),
            ]
        ]
    )
    await callback.message.edit_text(
        f"👑 Выдать пользователю <code>{uid}</code> VIP на 30 дней?",
        parse_mode="HTML",
        reply_markup=kb,
    )


@router.callback_query(F.data.startswith("admin_confirm_mute_"))
async def confirm_mute(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return

    uid = int(callback.data.rsplit("_", 1)[1])
    await callback.answer()
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Мут 24 часа",
                    callback_data=f"admin_do_mute_{uid}",
                ),
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data=f"admin_user_card_{uid}",
                ),
            ]
        ]
    )
    await callback.message.edit_text(
        f"🔇 Ограничить пользователя <code>{uid}</code> на 24 часа?",
        parse_mode="HTML",
        reply_markup=kb,
    )


@router.callback_query(F.data.startswith("admin_confirm_ban_"))
async def confirm_ban(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return

    uid = int(callback.data.rsplit("_", 1)[1])
    await callback.answer()
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⛔ Забанить навсегда",
                    callback_data=f"admin_do_ban_{uid}",
                ),
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data=f"admin_user_card_{uid}",
                ),
            ]
        ]
    )
    await callback.message.edit_text(
        (
            "⚠️ <b>Подтверждение</b>\n\n"
            f"Забанить пользователя <code>{uid}</code> навсегда?"
        ),
        parse_mode="HTML",
        reply_markup=kb,
    )


@router.callback_query(F.data.startswith("admin_do_mute_"))
async def admin_do_mute(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return

    uid = int(callback.data.rsplit("_", 1)[1])
    await _cleanup_user_session_before_restriction(
        callback.bot,
        uid,
    )
    await db.block_user(
        uid,
        True,
        datetime.now() + timedelta(hours=24),
    )
    await _admin_audit(
        callback.from_user.id,
        uid,
        "mute",
        "24h; source=admin_card",
    )

    try:
        await _send_restriction_notice(
            callback.bot,
            uid,
            permanent=False,
        )
    except Exception:
        pass

    await _log_admin_restriction(callback.bot, callback.from_user, uid, "Мут на 24 часа")
    await callback.answer("Мут выдан", show_alert=True)
    await refresh_admin_user_message(
        callback.message,
        uid,
        "✅ Мут на 24 часа выдан",
    )


@router.callback_query(F.data.startswith("admin_do_ban_"))
async def admin_do_ban(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return

    uid = int(callback.data.rsplit("_", 1)[1])
    await _cleanup_user_session_before_restriction(
        callback.bot,
        uid,
    )
    await db.block_user(uid, True)
    await _admin_audit(
        callback.from_user.id,
        uid,
        "ban",
        "permanent; source=admin_card",
    )

    try:
        await _send_restriction_notice(
            callback.bot,
            uid,
            permanent=True,
        )
    except Exception:
        pass

    await _log_admin_restriction(callback.bot, callback.from_user, uid, "Бессрочная блокировка")
    await callback.answer(
        "Пользователь забанен",
        show_alert=True,
    )
    await refresh_admin_user_message(
        callback.message,
        uid,
        "✅ Пользователь забанен",
    )


@router.callback_query(F.data.startswith("admin_unblock_"))
async def admin_unblock(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return

    uid = int(callback.data.rsplit("_", 1)[1])
    await db.block_user(uid, False)
    await _admin_audit(
        callback.from_user.id,
        uid,
        "unblock",
        "source=admin_card",
    )
    await _notify_restriction_removed(callback.bot, uid)
    await _log_admin_restriction(callback.bot, callback.from_user, uid, "Ограничение снято")

    await callback.answer(
        "Ограничение снято",
        show_alert=True,
    )
    await refresh_admin_user_message(
        callback.message,
        uid,
        "✅ Ограничение снято",
    )


@router.callback_query(F.data.startswith("admin_unwarn_"))
async def admin_unwarn(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return

    uid = int(callback.data.rsplit("_", 1)[1])
    async with aiosqlite.connect(db.DB_PATH) as conn:
        await conn.execute(
            "UPDATE users "
            "SET warnings=MAX(0,warnings-1) "
            "WHERE user_id=?",
            (uid,),
        )
        await conn.commit()

    await _admin_audit(
        callback.from_user.id,
        uid,
        "unwarn",
        "source=admin_card",
    )
    await callback.answer(
        "Одно предупреждение снято",
        show_alert=True,
    )
    await refresh_admin_user_message(
        callback.message,
        uid,
        "✅ Одно предупреждение снято",
    )


@router.callback_query(F.data.startswith("admin_user_history_"))
async def admin_user_history(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return

    uid = int(callback.data.rsplit("_", 1)[1])
    await callback.answer()

    async with aiosqlite.connect(db.DB_PATH) as conn:
        rows = await (
            await conn.execute(
                "SELECT action, details, timestamp "
                "FROM logs WHERE user_id=? "
                "ORDER BY id DESC LIMIT 20",
                (uid,),
            )
        ).fetchall()

    text = f"📜 <b>История пользователя</b> <code>{uid}</code>\n\n"
    if rows:
        text += "\n\n".join(
            (
                f"• <b>{html.escape(action)}</b>\n"
                f"{html.escape(details or '')}\n"
                f"<i>{html.escape(timestamp)}</i>"
            )
            for action, details, timestamp in rows
        )
    else:
        text += "История пока пуста."

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="↩️ К карточке",
                    callback_data=f"admin_user_card_{uid}",
                )
            ]
        ]
    )
    await callback.message.edit_text(
        text[-3900:],
        parse_mode="HTML",
        reply_markup=kb,
    )


@router.callback_query(F.data.startswith("admin_logs_filter_"))
async def admin_logs_filter(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return

    kind = callback.data.rsplit("_", 1)[1]
    await callback.answer()

    path = Path(BASE_DIR) / "logs" / "bot.log"
    lines = (
        path.read_text(
            encoding="utf-8",
            errors="replace",
        ).splitlines()
        if path.exists()
        else []
    )

    needles = {
        "errors": ["error", "exception", "traceback"],
        "admins": ["admin"],
        "payments": ["payment", "purchase", "withdraw", "stars"],
        "complaints": ["complaint", "жалоб"],
    }.get(kind, [])

    found = [
        line
        for line in lines
        if not needles or any(needle in line.lower() for needle in needles)
    ][-30:]

    text = (
        "📋 <b>Отфильтрованные записи</b>\n\n"
        "<pre>"
        + html.escape("\n".join(found)[-3500:] or "Записей нет")
        + "</pre>"
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="↩️ Назад",
                    callback_data="admin_logs_menu",
                )
            ]
        ]
    )
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=kb,
    )

async def _admin_scalar(connection, sql: str, params=()):
    row = await (await connection.execute(sql, params)).fetchone()
    return int((row[0] if row else 0) or 0)


def _admin_stats_back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="↩️ Назад", callback_data="admin_back_to_users")]
    ])


@router.callback_query(F.data == "admin_stats_chat")
async def admin_stats_chat(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    await callback.answer()
    today = datetime.now().date().isoformat()
    async with aiosqlite.connect(db.DB_PATH, timeout=10) as connection:
        total_users = await _admin_scalar(connection, "SELECT COUNT(*) FROM users")
        new_today = await _admin_scalar(connection, "SELECT COUNT(*) FROM users WHERE joined_date LIKE ?", (f"{today}%",))
        blocked = await _admin_scalar(connection, "SELECT COUNT(*) FROM users WHERE blocked=1")
        vip_bought = await _admin_scalar(connection, "SELECT COUNT(*) FROM logs WHERE action='successful_payment' AND details LIKE 'vip_subscription%'")
        queue_count = await _admin_scalar(connection, "SELECT COUNT(*) FROM queues")
        active_chats = await _admin_scalar(connection, "SELECT COUNT(*) FROM active_chats") // 2
        gifts = await _admin_scalar(connection, "SELECT COUNT(*) FROM purchases WHERE type='gift'")
        gifts_today = await _admin_scalar(connection, "SELECT COUNT(*) FROM purchases WHERE type='gift' AND timestamp LIKE ?", (f"{today}%",))
        stars = await _admin_scalar(connection, "SELECT COALESCE(SUM(price_stars),0) FROM purchases WHERE type NOT LIKE 'question_%'")
        reveal_income = await _admin_scalar(connection, "SELECT COALESCE(SUM(price_stars),0) FROM purchases WHERE type='reveal'")

    text = (
        "💬 <b>Анонимный чат</b>\n\n"
        "👥 <b>Пользователи</b>\n"
        f"├ Всего: <b>{total_users}</b>\n"
        f"├ Новых за сегодня: <b>{new_today}</b>\n"
        f"├ Заблокировали бота: <b>{blocked}</b>\n"
        f"└ Куплено VIP-подписок: <b>{vip_bought}</b>\n\n"
        "💬 <b>Общение</b>\n"
        f"├ В очереди: <b>{queue_count}</b>\n"
        f"└ Активных диалогов: <b>{active_chats}</b>\n\n"
        "🎁 <b>Активность и платежи</b>\n"
        f"├ Отправлено подарков: <b>{gifts}</b>\n"
        f"├ Подарков за сутки: <b>{gifts_today}</b>\n"
        f"├ Заработано звёзд: <b>{stars} ⭐</b>\n"
        f"└ Заработано на раскрытии: <b>{reveal_income} ⭐</b>"
    )
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=_admin_stats_back_kb())
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=_admin_stats_back_kb())


@router.callback_query(F.data == "admin_stats_questions")
async def admin_stats_questions(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    await callback.answer()
    async with aiosqlite.connect(db.DB_PATH, timeout=10) as connection:
        views = await _admin_scalar(connection, "SELECT COUNT(*) FROM question_link_visits")
        stayed = await _admin_scalar(connection, "SELECT COUNT(DISTINCT visitor_id) FROM question_link_visits")
        questions = await _admin_scalar(connection, "SELECT COUNT(*) FROM anonymous_questions")
        answers = await _admin_scalar(connection, "SELECT COUNT(*) FROM anonymous_questions WHERE answer_text IS NOT NULL")
        reveals = await _admin_scalar(connection, "SELECT COUNT(*) FROM purchases WHERE type='question_reveal'")
        gifts = await _admin_scalar(connection, "SELECT COUNT(*) FROM purchases WHERE type='question_gift'")
        vip = await _admin_scalar(connection, "SELECT COUNT(*) FROM purchases WHERE type='question_vip'")
        premium = await _admin_scalar(connection, "SELECT COUNT(*) FROM purchases WHERE type='question_premium'")
        reveal_income = await _admin_scalar(connection, "SELECT COALESCE(SUM(price_stars),0) FROM purchases WHERE type='question_reveal'")
        gift_income = await _admin_scalar(connection, "SELECT COALESCE(SUM(price_stars),0) FROM purchases WHERE type='question_gift'")
        stars_income = await _admin_scalar(connection, "SELECT COALESCE(SUM(price_stars),0) FROM purchases WHERE type='question_stars'")
        vip_income = await _admin_scalar(connection, "SELECT COALESCE(SUM(price_stars),0) FROM purchases WHERE type='question_vip'")
        premium_income = await _admin_scalar(connection, "SELECT COALESCE(SUM(price_stars),0) FROM purchases WHERE type='question_premium'")
    total = reveal_income + gift_income + stars_income + vip_income + premium_income
    text = (
        "❓ <b>Анонимные вопросы</b>\n\n"
        "❓ <b>Пользователи</b>\n"
        f"├ Переходов по ссылкам: <b>{views}</b>\n"
        f"├ Остались в боте: <b>{stayed}</b>\n"
        f"├ Получено вопросов: <b>{questions}</b>\n"
        f"├ Отправлено ответов: <b>{answers}</b>\n"
        f"├ Раскрытий: <b>{reveals}</b>\n"
        f"├ Подарков: <b>{gifts}</b>\n"
        f"├ Подарено VIP: <b>{vip}</b>\n"
        f"└ Подарено Telegram Premium: <b>{premium}</b>\n\n"
        "💰 <b>Доход с анонимных вопросов</b>\n"
        f"├ Раскрытия: <b>{reveal_income} ⭐</b>\n"
        f"├ Подарки: <b>{gift_income} ⭐</b>\n"
        f"├ Звёзды: <b>{stars_income} ⭐</b>\n"
        f"├ VIP статусы: <b>{vip_income} ⭐</b>\n"
        f"├ Telegram Premium: <b>{premium_income} ⭐</b>\n"
        f"└ Итого: <b>{total} ⭐</b>"
    )
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=_admin_stats_back_kb())
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=_admin_stats_back_kb())


def _xlsx_bytes(title: str, headers: list[str], rows: list[tuple]) -> bytes:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = title[:31]
    sheet.append(headers)
    for cell in sheet[1]:
        cell.font = openpyxl.styles.Font(bold=True)
    for row in rows:
        sheet.append(list(row))
    for column in sheet.columns:
        width = min(45, max(12, max(len(str(cell.value or "")) for cell in column) + 2))
        sheet.column_dimensions[column[0].column_letter].width = width
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


@router.callback_query(F.data == "admin_report_chat")
async def admin_report_chat(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    await callback.answer("Формирую отчёт…")
    async with aiosqlite.connect(db.DB_PATH, timeout=10) as connection:
        rows = await (await connection.execute(
            "SELECT timestamp,type,buyer_id,receiver_id,gift_id,price_stars "
            "FROM purchases WHERE type NOT LIKE 'question_%' ORDER BY id DESC"
        )).fetchall()
    data = _xlsx_bytes(
        "Анонимный чат",
        ["Дата", "Тип", "Отправитель ID", "Получатель ID", "Подарок ID", "Stars"],
        rows,
    )
    await callback.message.answer_document(
        BufferedInputFile(data, filename=f"casper_chat_report_{datetime.now():%Y%m%d_%H%M}.xlsx"),
        caption="📥 Отчёт по анонимному чату",
    )


@router.callback_query(F.data == "admin_report_questions")
async def admin_report_questions(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    await callback.answer("Формирую отчёт…")
    async with aiosqlite.connect(db.DB_PATH, timeout=10) as connection:
        payment_rows = await (await connection.execute(
            "SELECT timestamp,type,buyer_id,receiver_id,gift_id,price_stars "
            "FROM purchases WHERE type LIKE 'question_%' ORDER BY id DESC"
        )).fetchall()
        question_rows = await (await connection.execute(
            "SELECT created_at,'question',sender_id,receiver_id,public_id,0 FROM anonymous_questions ORDER BY id DESC"
        )).fetchall()
        answer_rows = await (await connection.execute(
            "SELECT answered_at,'answer',receiver_id,sender_id,public_id,0 FROM anonymous_questions "
            "WHERE answered_at IS NOT NULL ORDER BY id DESC"
        )).fetchall()
        visit_rows = await (await connection.execute(
            "SELECT created_at,'link_view',visitor_id,owner_id,'',0 FROM question_link_visits ORDER BY id DESC"
        )).fetchall()
    rows = sorted([*payment_rows, *question_rows, *answer_rows, *visit_rows], key=lambda row: str(row[0] or ""), reverse=True)
    data = _xlsx_bytes(
        "Анонимные вопросы",
        ["Дата", "Тип события", "Отправитель ID", "Получатель ID", "Вопрос / подарок ID", "Stars"],
        rows,
    )
    await callback.message.answer_document(
        BufferedInputFile(data, filename=f"casper_questions_report_{datetime.now():%Y%m%d_%H%M}.xlsx"),
        caption="📥 Отчёт по анонимным вопросам",
    )
