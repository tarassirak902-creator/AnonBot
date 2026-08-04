from .shared import *

@router.callback_query(
    Broadcast.waiting_for_confirmation,
    F.data == "cancel_broadcast",
)
async def broadcast_cancel(
    callback: types.CallbackQuery,
    state: FSMContext,
):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(
            "Недостаточно прав.",
            show_alert=True,
        )
        return

    await state.clear()
    await callback.answer("Рассылка отменена.")

    try:
        await callback.message.edit_text("❌ Рассылка отменена.")
    except Exception as exc:
        await db.log_action(
            callback.from_user.id,
            "broadcast_cancel_message_error",
            str(exc),
        )


@router.callback_query(
    Broadcast.waiting_for_confirmation,
    F.data == "confirm_broadcast",
)
async def broadcast_confirm(
    callback: types.CallbackQuery,
    state: FSMContext,
):
    admin_id = callback.from_user.id

    if admin_id not in ADMIN_IDS:
        await callback.answer(
            "Недостаточно прав.",
            show_alert=True,
        )
        return

    data = await state.get_data()

    msg_id = data.get("msg_id")
    chat_id = data.get("chat_id")
    button_text = data.get("button_text")
    button_url = data.get("button_url")
    extra_text = data.get("extra_text")

    if not msg_id or not chat_id:
        await state.clear()
        await callback.answer(
            "Исходное сообщение рассылки не найдено. Создайте рассылку заново.",
            show_alert=True,
        )
        return

    broadcast_kb = None

    if button_text and button_url:
        broadcast_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=button_text,
                        url=button_url,
                    )
                ]
            ]
        )

    await state.clear()
    await callback.answer("Рассылка запущена.")

    try:
        await callback.message.edit_text(
            "⏳ <b>Рассылка запущена. Пожалуйста, подождите...</b>",
            parse_mode="HTML",
        )
    except Exception as exc:
        await db.log_action(
            admin_id,
            "broadcast_status_message_error",
            str(exc),
        )

    users = await db.get_all_active_users()

    successful = 0
    blocked = 0
    other_errors = 0

    for user_id in users:
        try:
            await callback.bot.copy_message(
                chat_id=user_id,
                from_chat_id=chat_id,
                message_id=msg_id,
                reply_markup=broadcast_kb,
            )

            if extra_text:
                await callback.bot.send_message(
                    chat_id=user_id,
                    text=extra_text,
                    parse_mode="HTML",
                )

            successful += 1

        except Exception as exc:
            error_text = str(exc)
            normalized_error = error_text.lower()

            blocked_markers = (
                "forbidden",
                "bot was blocked",
                "user is deactivated",
                "chat not found",
            )

            if any(
                marker in normalized_error
                for marker in blocked_markers
            ):
                blocked += 1
                await db.log_action(
                    admin_id,
                    "broadcast_unreachable",
                    (
                        f"user_id={user_id}; "
                        f"error={error_text}"
                    ),
                )
            else:
                other_errors += 1
                await db.log_action(
                    admin_id,
                    "broadcast_delivery_error",
                    (
                        f"user_id={user_id}; "
                        f"error={error_text}"
                    ),
                )

        finally:
            # Небольшая пауза снижает риск ограничений Telegram.
            await asyncio.sleep(0.05)

    report_details = (
        f"total={len(users)}; "
        f"successful={successful}; "
        f"blocked={blocked}; "
        f"errors={other_errors}"
    )

    await db.log_action(
        admin_id,
        "broadcast_completed",
        report_details,
    )

    report_text = (
        "✅ <b>Рассылка завершена!</b>\n\n"
        "📊 <b>Статистика отправки:</b>\n"
        f"👥 Всего пользователей: <b>{len(users)}</b>\n"
        f"📥 Доставлено: <b>{successful}</b>\n"
        f"🚫 Недоступно: <b>{blocked}</b>\n"
        f"⚠️ Другие ошибки: <b>{other_errors}</b>"
    )

    await callback.message.answer(
        report_text,
        parse_mode="HTML",
    )


@router.callback_query(F.data == "admin_download_users")
async def download_users_file(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: return
    await callback.answer("⏳ Формируем Excel-таблицу...")

    async with aiosqlite.connect(db.DB_PATH) as connection:
        cursor = await connection.execute("SELECT user_id, username, first_name, last_name FROM users ORDER BY ROWID ASC")
        rows = await cursor.fetchall()

    if not rows:
        await callback.message.answer("❌ База пользователей пуста.")
        return

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Пользователи"
    headers = ["№", "ID", "Username", "Имя", "Фамилия"]
    ws.append(headers)

    for idx, user in enumerate(rows, 1):
        uid, username, first_name, last_name = user
        ws.append([idx, uid, f"@{username}" if username else "—", first_name or "—", last_name or "—"])

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    input_file = BufferedInputFile(output.getvalue(), filename=f"users_table_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx")
    await callback.message.answer_document(document=input_file, caption=f"📊 **Таблица пользователей готова!** (Всего: {len(rows)})", parse_mode="Markdown")

