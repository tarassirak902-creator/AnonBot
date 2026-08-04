from __future__ import annotations

from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.core.ui_copy import screen

from . import questions


async def save_question_ui(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text or len(text) > 1500:
        await message.answer(
            screen(
                "⚠️ Проверьте вопрос",
                intro="Текст должен содержать от 1 до 1 500 символов.",
            ),
            parse_mode="HTML",
        )
        return

    data = await state.get_data()
    receiver_raw = data.get("question_target_id")
    if not receiver_raw:
        await message.answer(
            screen(
                "❌ Получатель недоступен",
                intro="Откройте персональную ссылку заново.",
            ),
            parse_mode="HTML",
        )
        await state.clear()
        return

    receiver_id = int(receiver_raw)
    name = data.get("question_target_name", "пользователю")
    public_id = await questions.db.create_anonymous_question(
        message.from_user.id,
        receiver_id,
        text,
    )
    active_chat = await questions.db.get_partner(receiver_id)

    try:
        if active_chat:
            await questions.db.set_question_chat_pending(public_id, True)
            notice = screen(
                "❓ Новый анонимный вопрос",
                intro="Вопрос поступил во время активного диалога.",
                footer="Он будет доступен после завершения общения.",
            )
        else:
            notice = screen(
                "❓ Новый анонимный вопрос",
                intro="Откройте раздел «Вопросы», чтобы прочитать его.",
            )
        await message.bot.send_message(receiver_id, notice, parse_mode="HTML")
    except Exception:
        pass

    await questions.db.log_action(
        message.from_user.id,
        "question_sent",
        f"question={public_id}; receiver={receiver_id}",
    )
    await state.set_state(questions.AnonymousQuestionFlow.target_menu)
    await message.answer(
        screen(
            "✅ Вопрос отправлен",
            intro="Получатель увидит его без вашего имени.",
            footer="Теперь можно дождаться ответа или отправить что-то ещё.",
        ),
        parse_mode="HTML",
        reply_markup=questions.question_target_inline(name),
    )


async def send_answer_ui(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    public_id = data.get("answer_question_id")
    answer_text = (message.text or "").strip()

    if not answer_text or len(answer_text) > 1500:
        await message.answer(
            screen(
                "⚠️ Проверьте ответ",
                intro="Текст должен содержать от 1 до 1 500 символов.",
            ),
            parse_mode="HTML",
        )
        return

    result = await questions.db.answer_question(
        public_id,
        message.from_user.id,
        answer_text,
    )
    if not result:
        await message.answer(
            screen(
                "❌ Вопрос недоступен",
                intro="Он мог быть удалён или уже обработан.",
            ),
            parse_mode="HTML",
            reply_markup=questions.main_menu(
                message.from_user.id in questions.ADMIN_IDS
            ),
        )
        await state.clear()
        return

    sender_id, _question_text = result
    active_chat = await questions.db.get_partner(sender_id)
    try:
        if active_chat:
            await questions.db.set_answer_chat_pending(public_id, True)
            notice = screen(
                "💬 Получен ответ",
                intro="Ответ поступил во время активного диалога.",
                footer="Он будет доступен после завершения общения.",
            )
        else:
            notice = screen(
                "💬 Получен ответ",
                intro="Откройте раздел «Вопросы», чтобы прочитать его.",
            )
        await message.bot.send_message(sender_id, notice, parse_mode="HTML")
    except Exception:
        pass

    await questions.db.log_action(
        message.from_user.id,
        "question_answered",
        f"question={public_id}; sender={sender_id}",
    )
    await state.set_state(questions.AnonymousQuestionFlow.viewing_question)
    await state.update_data(current_question_id=public_id)
    await message.answer(
        screen(
            "✅ Ответ отправлен",
            intro="Автор вопроса получил уведомление.",
        ),
        parse_mode="HTML",
        reply_markup=questions.question_card_menu(),
    )


def _replace_message_handler(name: str, callback) -> bool:
    for handler in questions.router.message.handlers:
        if getattr(handler.callback, "__name__", "") == name:
            handler.callback = callback
            return True
    return False


def install_question_delivery_ui() -> None:
    replaced_question = _replace_message_handler("save_question", save_question_ui)
    replaced_answer = _replace_message_handler("send_answer", send_answer_ui)
    if not replaced_question or not replaced_answer:
        raise RuntimeError("Question delivery handlers were not found")
