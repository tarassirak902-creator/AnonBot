from .shared import *

# =====================================================================
# 3. АДМИН-КОМАНДЫ ПРЯМОГО ВВОДА
# =====================================================================

@router.message(Command("reset_all"))
async def cmd_reset_all_users(
    message: Message,
    state: FSMContext,
):
    if message.from_user.id not in ADMIN_IDS:
        return

    await message.answer(
        "⏳ <b>Запущен полный сброс всех пользователей...</b>",
        parse_mode="HTML",
    )

    await db.clear_all_chats_and_queues()
    users = await db.get_all_active_users()

    success_count = 0
    failed_count = 0

    welcome_text = (
        await db.get_setting("welcome_text")
        or "Приветствуем в анонимном чате!"
    )

    for uid in users:
        try:
            temp_msg = await message.bot.send_message(
                chat_id=uid,
                text="🔄 <i>Система бота была обновлена.</i>",
                reply_markup=ReplyKeyboardRemove(),
                parse_mode="HTML",
            )

            await message.bot.send_message(
                chat_id=uid,
                text=(
                    f"{welcome_text}\n\n"
                    "Нажмите кнопку ниже, чтобы начать поиск:"
                ),
                reply_markup=main_menu(uid in ADMIN_IDS),
            )

            await safe_delete_message(temp_msg)
            success_count += 1

        except Exception as exc:
            failed_count += 1
            await db.log_action(
                message.from_user.id,
                "reset_all_delivery_error",
                f"user_id={uid}; error={exc}",
            )

        await asyncio.sleep(0.05)

    await db.log_action(
        message.from_user.id,
        "reset_all_completed",
        (
            f"total={len(users)}; "
            f"success={success_count}; "
            f"failed={failed_count}"
        ),
    )

    await message.answer(
        (
            "✅ <b>Сброс завершён!</b>\n\n"
            f"👤 Всего пользователей: <b>{len(users)}</b>\n"
            f"✅ Обновлено: <b>{success_count}</b>\n"
            f"⚠️ Недоступно: <b>{failed_count}</b>"
        ),
        parse_mode="HTML",
    )


@router.message(Command("addword"))
async def add_banned_word_cmd(message: Message):
    if message.from_user.id not in ADMIN_IDS: return
    word = message.text.partition(" ")[2]
    if word:
        await db.add_banned_word(word)
        await message.answer(f"Слово '{word}' добавлено.")
    else: await message.answer("Укажите слово: /addword слово")

@router.message(Command("delword"))
async def del_banned_word_cmd(message: Message):
    if message.from_user.id not in ADMIN_IDS: return
    word = message.text.partition(" ")[2]
    if word:
        await db.remove_banned_word(word)
        await message.answer(f"Слово '{word}' удалено.")
    else: await message.answer("Укажите слово: /delword слово")

@router.message(Command("addgift"))
async def add_gift_cmd(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS: return
    await message.answer("Введите параметры подарка. Пример: Роза 🌹 15")
    await state.set_state(GiftAdd.waiting_for_name)

@router.message(Command("delgift"))
async def del_gift_cmd(message: Message):
    if message.from_user.id not in ADMIN_IDS: return
    try:
        gid = int(message.text.split()[1])
        await db.delete_gift(gid)
        await message.answer("Подарок удалён.")
    except (ValueError, IndexError):
        await message.answer("Укажите ID: /delgift ID")


