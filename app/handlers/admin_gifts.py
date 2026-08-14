from .shared import *


async def gifts_admin_screen(message):
    gifts = await db.get_all_gifts()
    text = "🎁 <b>Управление подарками</b>\n\n" + (
        "\n".join(f"• {g[2]} {g[1]} — {g[3]} ⭐ (ID {g[0]})" for g in gifts)
        if gifts
        else "Подарков нет."
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить подарок", callback_data="admin_gift_add")],
            [InlineKeyboardButton(text="🗑 Выбрать подарки для удаления", callback_data="admin_gift_delete_menu")],
            [InlineKeyboardButton(text="↩️ Назад", callback_data="admin_back_to_panel")],
        ]
    )
    await message.answer(text, parse_mode="HTML", reply_markup=kb)


@router.message(F.text == "🎁 Управление подарками")
async def gifts_management(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    await state.clear()
    await gifts_admin_screen(message)


@router.callback_query(F.data == "admin_gift_add")
async def admin_gift_add(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        return
    await callback.answer()
    await state.set_state(GiftAdd.waiting_for_name)
    await callback.message.edit_text(
        "Введите подарок в формате:\n<code>Название Эмодзи Цена</code>\nПример: <code>Роза 🌹 25</code>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="↩️ Назад", callback_data="admin_gifts_menu")]
            ]
        ),
    )


@router.message(GiftAdd.waiting_for_name)
async def admin_gift_add_receive(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    parts = (message.text or "").rsplit(maxsplit=2)
    if len(parts) != 3 or not parts[2].isdigit() or int(parts[2]) <= 0:
        await message.answer("❌ Формат: Название Эмодзи Цена. Например: Роза 🌹 25")
        return
    name, emoji, price = parts[0].strip(), parts[1].strip(), int(parts[2])
    await db.add_gift(name, emoji, price)
    await state.clear()
    await message.answer(f"✅ Добавлен подарок: {emoji} {name} — {price} ⭐")
    await gifts_admin_screen(message)


async def gift_delete_keyboard(selected):
    gifts = await db.get_all_gifts()
    rows = []
    for gift in gifts:
        mark = "✅" if gift[0] in selected else "⬜"
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{mark} {gift[2]} {gift[1]} — {gift[3]} ⭐",
                    callback_data=f"admin_gift_toggle_{gift[0]}",
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text=f"🗑 Удалить выбранные ({len(selected)})",
                callback_data="admin_gift_delete_confirm",
            )
        ]
    )
    rows.append([InlineKeyboardButton(text="↩️ Назад", callback_data="admin_gifts_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data == "admin_gift_delete_menu")
async def admin_gift_delete_menu(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        return
    await callback.answer()
    await state.set_state(GiftDeleteSelect.selecting)
    await state.update_data(selected_gifts=[])
    await callback.message.edit_text(
        "Отметьте один или несколько подарков:",
        reply_markup=await gift_delete_keyboard(set()),
    )


@router.callback_query(F.data.startswith("admin_gift_toggle_"))
async def admin_gift_toggle(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        return
    gift_id = int(callback.data.rsplit("_", 1)[1])
    data = await state.get_data()
    selected = set(data.get("selected_gifts", []))
    if gift_id in selected:
        selected.remove(gift_id)
    else:
        selected.add(gift_id)
    await state.update_data(selected_gifts=list(selected))
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=await gift_delete_keyboard(selected))


@router.callback_query(F.data == "admin_gift_delete_confirm")
async def admin_gift_delete_confirm(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        return
    selected = set((await state.get_data()).get("selected_gifts", []))
    if not selected:
        await callback.answer("Сначала выберите подарки", show_alert=True)
        return
    for gift_id in selected:
        await db.delete_gift(gift_id)
    await state.clear()
    await callback.answer(f"Удалено подарков: {len(selected)}", show_alert=True)
    gifts = await db.get_all_gifts()
    text = "🎁 <b>Управление подарками</b>\n\n" + (
        "\n".join(f"• {g[2]} {g[1]} — {g[3]} ⭐" for g in gifts)
        if gifts
        else "Подарков нет."
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить подарок", callback_data="admin_gift_add")],
            [InlineKeyboardButton(text="🗑 Выбрать подарки для удаления", callback_data="admin_gift_delete_menu")],
            [InlineKeyboardButton(text="↩️ Назад", callback_data="admin_back_to_panel")],
        ]
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data == "admin_gifts_menu")
async def admin_gifts_menu_callback(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        return
    await state.clear()
    await callback.answer()
    gifts = await db.get_all_gifts()
    text = "🎁 <b>Управление подарками</b>\n\n" + (
        "\n".join(f"• {g[2]} {g[1]} — {g[3]} ⭐" for g in gifts)
        if gifts
        else "Подарков нет."
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить подарок", callback_data="admin_gift_add")],
            [InlineKeyboardButton(text="🗑 Выбрать подарки для удаления", callback_data="admin_gift_delete_menu")],
            [InlineKeyboardButton(text="↩️ Назад", callback_data="admin_back_to_panel")],
        ]
    )
    await safe_delete_message(callback.message)
    await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)
