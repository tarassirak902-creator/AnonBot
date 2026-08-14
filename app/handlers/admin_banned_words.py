from .shared import *


async def banned_words_screen(message):
    words = await db.get_banned_words()
    text = "🚫 <b>Запрещённые слова</b>\n\n" + (
        "\n".join(f"• {w}" for w in words) if words else "Список пуст."
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить слово", callback_data="admin_word_add")],
            [InlineKeyboardButton(text="➖ Удалить слово", callback_data="admin_word_delete_menu")],
            [InlineKeyboardButton(text="↩️ Назад", callback_data="admin_back_to_panel")],
        ]
    )
    await message.answer(text, parse_mode="HTML", reply_markup=kb)


@router.message(F.text == "🚫 Запрещённые слова")
async def banned_words(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    await state.clear()
    await banned_words_screen(message)


@router.callback_query(F.data == "admin_word_add")
async def admin_word_add(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        return
    await callback.answer()
    await state.set_state(BannedWordAdd.waiting_for_word)
    await callback.message.edit_text(
        "➕ Отправьте запрещённое слово или фразу:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="↩️ Назад", callback_data="admin_words_menu")]
            ]
        ),
    )


@router.message(BannedWordAdd.waiting_for_word)
async def admin_word_add_receive(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    word = (message.text or "").strip()
    if not word or len(word) > 100:
        await message.answer("❌ Введите слово или фразу длиной до 100 символов.")
        return
    await db.add_banned_word(word)
    await state.clear()
    await message.answer(f"✅ Добавлено: <b>{word}</b>", parse_mode="HTML")
    await banned_words_screen(message)


@router.callback_query(F.data.in_({"admin_words_menu", "admin_word_delete_menu"}))
async def admin_words_callbacks(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        return
    await state.clear()
    await callback.answer()
    words = await db.get_banned_words()

    if callback.data == "admin_word_delete_menu":
        rows = [
            [InlineKeyboardButton(text=f"❌ {word}", callback_data=f"admin_word_delete:{index}")]
            for index, word in enumerate(words)
        ]
        rows.append([InlineKeyboardButton(text="↩️ Назад", callback_data="admin_words_menu")])
        await state.update_data(word_delete_list=words)
        await callback.message.edit_text(
            "Выберите слово для удаления:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
        )
        return

    text = "🚫 <b>Запрещённые слова</b>\n\n" + (
        "\n".join(f"• {word}" for word in words) if words else "Список пуст."
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить слово", callback_data="admin_word_add")],
            [InlineKeyboardButton(text="➖ Удалить слово", callback_data="admin_word_delete_menu")],
            [InlineKeyboardButton(text="↩️ Назад", callback_data="admin_back_to_panel")],
        ]
    )
    await safe_delete_message(callback.message)
    await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data.startswith("admin_word_delete:"))
async def admin_word_delete(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        return
    data = await state.get_data()
    words = data.get("word_delete_list", [])
    try:
        word_index = int(callback.data.split(":", 1)[1])
        word = words[word_index]
    except (ValueError, IndexError):
        await callback.answer("Список устарел", show_alert=True)
        return

    await db.remove_banned_word(word)
    await callback.answer(f"Удалено: {word}", show_alert=True)
    remaining = await db.get_banned_words()
    await state.update_data(word_delete_list=remaining)
    rows = [
        [InlineKeyboardButton(text=f"❌ {item}", callback_data=f"admin_word_delete:{index}")]
        for index, item in enumerate(remaining)
    ]
    rows.append([InlineKeyboardButton(text="↩️ Назад", callback_data="admin_words_menu")])
    await callback.message.edit_text(
        "Выберите слово для удаления:" if remaining else "Список запрещённых слов пуст.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )
