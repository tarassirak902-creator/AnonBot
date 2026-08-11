from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from app.database.platform_automation_repository import build_dialog_key, create_rating_pair
from app.database.platform_missions_repository import record_mission_event

from . import shared


async def _post_dialog_feedback(bot, user1_id: int, user2_id: int, dialog_key: str) -> None:
    try:
        from .platform_automation_ui import send_rating_prompt

        ratings = await create_rating_pair(user1_id, user2_id, dialog_key=dialog_key)
        for pending in ratings:
            try:
                await send_rating_prompt(bot, pending)
            except Exception:
                pass
    except Exception:
        shared.logger.exception(
            "Не удалось создать rating prompt после таймаута: user1=%s user2=%s",
            user1_id,
            user2_id,
        )

    for uid in (user1_id, user2_id):
        try:
            await record_mission_event(uid, f"dialog:{dialog_key}:{uid}", "dialog_complete")
        except Exception:
            shared.logger.exception("Не удалось записать mission event: user_id=%s", uid)


async def safe_inactivity_timer_worker(bot, user1_id: int, user2_id: int) -> None:
    """Expire only the exact reciprocal chat pair that created this timer.

    Match notification failures and fast partner changes can leave an old sleeping
    task alive. Accounting and teardown are delegated to one database transaction,
    so an old timer can never clear or count a newer chat between a guard check and
    the teardown itself.
    """
    try:
        await asyncio.sleep(600)
        if not await shared.db.expire_chat_pair_if_active(user1_id, user2_id):
            return

        dialog_key = build_dialog_key(user1_id, user2_id, datetime.now(timezone.utc))
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
                f"timeout:{dialog_key}",
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

        await _post_dialog_feedback(bot, user1_id, user2_id, dialog_key)
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
