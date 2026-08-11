from __future__ import annotations

import asyncio

from . import shared


async def safe_inactivity_timer_worker(bot, user1_id: int, user2_id: int) -> None:
    """Expire only the exact reciprocal chat pair that created this timer.

    Match notification failures and fast partner changes can leave an old sleeping
    task alive. The task must never count time, tear down a newer chat, send ads or
    offer reveal unless the original pair is still active after the timeout.
    """
    try:
        await asyncio.sleep(600)
        if not await shared.db.is_active_chat_pair(user1_id, user2_id):
            return

        await shared.db.add_completed_chat_time(user1_id)
        await shared.db.add_completed_chat_time(user2_id)
        ended_partner = await shared.db.end_chat(user1_id)
        if ended_partner != user2_id:
            return

        shared.cancel_unread_reminder(user1_id)
        shared.cancel_unread_reminder(user2_id)

        for uid in (user1_id, user2_id):
            try:
                await bot.send_message(
                    uid,
                    "⌛ <b>Диалог завершён из-за неактивности (10 минут).</b>\n\n"
                    "Можете начать новый поиск!",
                    reply_markup=shared.main_menu(uid in shared.ADMIN_IDS),
                    parse_mode="HTML",
                )
            except Exception:
                shared.logger.exception(
                    "Не удалось уведомить о таймауте: user_id=%s", uid
                )

        try:
            from .advertising import send_ads_to_dialog_users

            await send_ads_to_dialog_users(
                bot,
                user1_id,
                user2_id,
                f"timeout:{min(user1_id, user2_id)}:{max(user1_id, user2_id)}",
            )
        except Exception:
            shared.logger.exception(
                "Не удалось обработать рекламу после таймаута: user1=%s user2=%s",
                user1_id,
                user2_id,
            )

        for uid, partner_id in ((user1_id, user2_id), (user2_id, user1_id)):
            try:
                await bot.send_message(
                    uid,
                    "Хотите узнать, с кем вы общались?",
                    reply_markup=shared.reveal_offer_kb(partner_id),
                )
            except Exception:
                shared.logger.exception(
                    "Не удалось отправить reveal-offer после таймаута: user_id=%s",
                    uid,
                )
            await shared.notify_pending_question_activity(bot, uid)
    except asyncio.CancelledError:
        return
    except Exception:
        shared.logger.exception(
            "Ошибка безопасного таймера неактивности: user1=%s user2=%s",
            user1_id,
            user2_id,
        )
    finally:
        current = asyncio.current_task()
        for uid in (user1_id, user2_id):
            if shared.chat_timeout_tasks.get(uid) is current:
                shared.chat_timeout_tasks.pop(uid, None)


def install_inactivity_timer_safety() -> None:
    shared.inactivity_timer_worker = safe_inactivity_timer_worker
