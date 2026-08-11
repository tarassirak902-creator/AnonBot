from .shared import *
from .shared import _log_background_task_error

# =====================================================================
# 7. ЧАТ И ПЕРЕСЫЛКА СООБЩЕНИЙ / ИММУНИТЕТ ДЛЯ VIP
# =====================================================================

async def log_media(message: Message, sender_id: int, receiver_id: int, media_type: str, caption: str):
    try:
        bot = message.bot
        sender = await bot.get_chat(sender_id)
        receiver = await bot.get_chat(receiver_id)
        
        s_name = f"{sender.first_name or ''} {sender.last_name or ''}".strip()
        s_un = f"@{sender.username}" if sender.username else "нет"
        r_name = f"{receiver.first_name or ''} {receiver.last_name or ''}".strip()
        r_un = f"@{receiver.username}" if receiver.username else "нет"
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        info = (
            f"📁 <b>МЕДИАФАЙЛ В ЧАТЕ ({html.escape(media_type.upper())})</b>\n\n"
            f"📝 <b>Подпись:</b> {html.escape(caption or 'нет')}\n"
            f"🕐 <b>Время:</b> {now}\n\n"
            f"👤 <b>Отправитель:</b>\n├ Имя: {html.escape(s_name)}\n├ Username: {html.escape(s_un)}\n└ ID: <code>{sender_id}</code>\n\n"
            f"💬 <b>Получатель:</b>\n├ Имя: {html.escape(r_name)}\n├ Username: {html.escape(r_un)}\n└ ID: <code>{receiver_id}</code>"
        )

        admin_kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="⚠️ Выдать варн", callback_data=f"log_warn_{sender_id}"),
                InlineKeyboardButton(text="🔇 Мут 24ч", callback_data=f"log_mute_{sender_id}"),
            ],
            [
                InlineKeyboardButton(text="⛔ Бан навсегда", callback_data=f"log_ban_{sender_id}")
            ]
        ])

        if media_type == "photo":
            await bot.send_photo(LOG_CHANNEL_ID, message.photo[-1].file_id, caption=info, parse_mode="HTML", reply_markup=admin_kb)
        elif media_type == "video":
            await bot.send_video(LOG_CHANNEL_ID, message.video.file_id, caption=info, parse_mode="HTML", reply_markup=admin_kb)
        elif media_type == "voice":
            await bot.send_voice(LOG_CHANNEL_ID, message.voice.file_id, caption=info, parse_mode="HTML", reply_markup=admin_kb)
        elif media_type == "animation":
            await bot.send_animation(LOG_CHANNEL_ID, message.animation.file_id, caption=info, parse_mode="HTML", reply_markup=admin_kb)
        elif media_type == "video_note":
            await bot.send_video_note(LOG_CHANNEL_ID, message.video_note.file_id)
            await bot.send_message(LOG_CHANNEL_ID, info, parse_mode="HTML", reply_markup=admin_kb)
        elif media_type == "sticker":
            await bot.send_sticker(LOG_CHANNEL_ID, message.sticker.file_id)
            await bot.send_message(LOG_CHANNEL_ID, info, parse_mode="HTML", reply_markup=admin_kb)

    except Exception as e:
        await db.log_action(sender_id, "log_media_error", str(e))

async def check_and_forward_text(message: Message):
    user_id = message.from_user.id
    partner_info = await db.get_partner(user_id)
    if not partner_info: return
    partner_id = partner_info

    is_vip = await db.is_user_vip(user_id)

    if not is_vip:
        if is_forwarded(message):
            await message.answer("⛔ Пересылка сообщений запрещена!")
            return

        if contains_links_or_usernames(message):
            await message.answer("⛔ Отправка ссылок и юзернеймов запрещена!")
            return

        if await db.contains_banned_word(message.text):
            await message.answer("⛔ Сообщение содержит запрещённые слова.")
            return

    try:
        await message.bot.send_message(partner_id, message.text, protect_content=True)
        await db.register_user_activity(user_id)
        cancel_unread_reminder(user_id)
        schedule_unread_reminder(message.bot, partner_id)
        reset_inactivity_timer(message.bot, user_id, partner_id)
    except Exception as e:
        await db.log_action(user_id, "send_error", str(e))

async def forward_media(message: Message, media_type: str):
    user_id = message.from_user.id
    partner_info = await db.get_partner(user_id)
    if not partner_info: return
    partner_id = partner_info

    is_vip = await db.is_user_vip(user_id)

    if not is_vip:
        if is_forwarded(message):
            await message.answer("⛔ Пересылка медиафайлов запрещена!")
            return

        caption = message.caption or ""
        if contains_links_or_usernames(message) or (caption and await db.contains_banned_word(caption)):
            await message.answer("⛔ Сообщение заблокировано фильтром безопасности.")
            return

    try:
        await message.copy_to(partner_id, protect_content=True)
        await db.register_user_activity(user_id)
        cancel_unread_reminder(user_id)
        schedule_unread_reminder(message.bot, partner_id)
        reset_inactivity_timer(message.bot, user_id, partner_id)
    except Exception as e:
        await db.log_action(user_id, "media_error", str(e))
        return

    task = asyncio.create_task(log_media(message, user_id, partner_id, media_type, message.caption or ""))
    task.add_done_callback(_log_background_task_error)

@router.message(F.photo, StateFilter(None))
async def handle_photo(message: Message): await forward_media(message, "photo")

@router.message(F.video, StateFilter(None))
async def handle_video(message: Message): await forward_media(message, "video")

@router.message(F.voice, StateFilter(None))
async def handle_voice(message: Message): await forward_media(message, "voice")

@router.message(F.video_note, StateFilter(None))
async def handle_video_note(message: Message): await forward_media(message, "video_note")

@router.message(F.animation, StateFilter(None))
async def handle_animation(message: Message): await forward_media(message, "animation")

@router.message(F.sticker, StateFilter(None))
async def handle_sticker(message: Message): await forward_media(message, "sticker")

@router.message(F.text, StateFilter(None))
async def handle_text(message: Message):
    user_id = message.from_user.id
    if not await db.get_partner(user_id): return

    ignored = ["Мини игры", "🎮 Мини-игры", "⚔️ Играть с собеседником", "🎁 Подарить подарок", "⭐ Кто собеседник", "⚠️ Пожаловаться", "➡️ Следующий собеседник", "❌ Завершить диалог"]
    if message.text in ignored: return

    await check_and_forward_text(message)
