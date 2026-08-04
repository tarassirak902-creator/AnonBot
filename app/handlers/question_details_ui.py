from __future__ import annotations

from datetime import datetime
from html import escape

from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice, Message

from app.core.ui_copy import screen
from app.core.ui_labels import ButtonText

from . import questions


def _stamp(value) -> str:
    try:
        return datetime.fromisoformat(str(value)).strftime("%d.%m.%Y • %H:%M")
    except (TypeError, ValueError):
        return str(value or "—")


async def send_question_author_ui(message: Message, sender_id: int) -> None:
    try:
        author = await message.bot.get_chat(sender_id)
        full_name = f"{author.first_name or ''} {author.last_name or ''}".strip() or "Не указано"
        username = f"@{author.username}" if author.username else "Не указан"
        text = screen(
            "👤 Автор вопроса",
            sections=(
                (
                    "Профиль",
                    (
                        f"Имя: <b>{escape(full_name)}</b>",
                        f"Username: <b>{escape(username)}</b>",
                        f"Telegram ID: <code>{author.id}</code>",
                    ),
                ),
            ),
            footer=f'<a href="tg://user?id={author.id}">Открыть профиль</a>',
        )
    except Exception:
        text = screen(
            "👤 Автор вопроса",
            intro=f'<a href="tg://user?id={sender_id}">Открыть профиль</a>',
        )
    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=questions.question_card_menu(author_revealed=True),
    )


async def question_view_ui(callback: CallbackQuery, state: FSMContext) -> None:
    public_id = callback.data.rsplit(":", 1)[1]
    row = await questions.db.get_question_by_public_id(public_id)
    if not row or int(row[3]) != callback.from_user.id:
        await callback.answer("Вопрос не найден.", show_alert=True)
        return

    await questions.db.mark_question_read(public_id, callback.from_user.id)
    qid, _, _, _, text, _status, answer, created_at, *_ = row
    sections = [("Вопрос", (f"«{escape(text)}»",))]
    if answer:
        sections.append(("Ваш ответ", (escape(answer),)))

    await questions._clear_question_screen(callback.message, state, delete_trigger=False)
    await state.set_state(questions.AnonymousQuestionFlow.viewing_question)
    await state.update_data(current_question_id=public_id)
    content = await callback.message.answer(
        screen(
            f"❓ Вопрос №{qid}",
            intro=f"Получен: <b>{_stamp(created_at)}</b>",
            sections=tuple(sections),
        ),
        parse_mode="HTML",
        reply_markup=questions.question_card_inline(author_revealed=bool(row[10])),
    )
    await questions._remember_question_screen(state, content)
    await callback.answer()


async def answer_view_ui(callback: CallbackQuery, state: FSMContext) -> None:
    public_id = callback.data.rsplit(":", 1)[1]
    row = await questions.db.get_question_by_public_id(public_id)
    if not row or int(row[2]) != callback.from_user.id or not row[6]:
        await callback.answer("Ответ не найден.", show_alert=True)
        return

    await questions.db.mark_question_answer_read(public_id, callback.from_user.id)
    qid, _, _, _, question_text, _, answer_text, _, _, answered_at, _ = row
    await questions._clear_question_screen(callback.message, state, delete_trigger=False)
    await state.set_state(questions.AnonymousQuestionFlow.viewing_answer)
    await state.update_data(current_answer_question_id=public_id)
    content = await callback.message.answer(
        screen(
            f"💬 Ответ на вопрос №{qid}",
            intro=f"Получен: <b>{_stamp(answered_at)}</b>",
            sections=(
                ("Ваш вопрос", (f"«{escape(question_text)}»",)),
                ("Ответ", (escape(answer_text),)),
            ),
        ),
        parse_mode="HTML",
        reply_markup=questions.answer_card_inline(),
    )
    await questions._remember_question_screen(state, content)
    await callback.answer()


async def buy_author_reveal_ui(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    public_id = data.get("current_question_id")
    row = await questions.db.get_question_by_public_id(public_id)
    if not row or int(row[3]) != message.from_user.id:
        await message.answer(screen("❌ Вопрос недоступен", intro="Вернитесь к списку вопросов."), parse_mode="HTML")
        return
    if bool(row[10]):
        await send_question_author_ui(message, int(row[2]))
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Оплатить 100 ⭐", pay=True)],
        [InlineKeyboardButton(text=ButtonText.CANCEL, callback_data=f"question_reveal_cancel:{public_id}")],
    ])
    invoice = await message.bot.send_invoice(
        chat_id=message.chat.id,
        title="Раскрытие автора вопроса",
        description="После оплаты вы увидите Telegram-профиль автора.",
        payload=f"question_reveal:{public_id}",
        currency="XTR",
        prices=[LabeledPrice(label="Узнать автора", amount=100)],
        reply_markup=keyboard,
    )
    questions.pending_invoice_message_ids[message.from_user.id] = invoice.message_id


async def cancel_author_reveal_ui(callback: CallbackQuery, state: FSMContext) -> None:
    public_id = callback.data.split(":", 1)[1]
    data = await state.get_data()
    if data.get("current_question_id") != public_id:
        await callback.answer("Счёт уже неактуален.", show_alert=True)
        return
    questions.pending_invoice_message_ids.pop(callback.from_user.id, None)
    try:
        await callback.message.delete()
    except Exception:
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
    await callback.answer("Оплата отменена.")


def _replace(observer, name: str, callback) -> bool:
    for handler in observer.handlers:
        if getattr(handler.callback, "__name__", "") == name:
            handler.callback = callback
            return True
    return False


def install_question_details_ui() -> None:
    questions._send_question_author = send_question_author_ui
    required = (
        _replace(questions.router.callback_query, "question_view", question_view_ui),
        _replace(questions.router.callback_query, "question_answer_view", answer_view_ui),
        _replace(questions.router.message, "buy_question_author_reveal", buy_author_reveal_ui),
        _replace(questions.router.callback_query, "cancel_question_author_reveal", cancel_author_reveal_ui),
    )
    if not all(required):
        raise RuntimeError("Question detail handlers were not found")
