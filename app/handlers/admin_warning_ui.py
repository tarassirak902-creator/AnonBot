from __future__ import annotations

from aiogram import F
from aiogram.types import CallbackQuery

from app.core.ui_copy import screen

from .shared import ADMIN_IDS, db, logger, router


def warning_notice(count: int, *, auto_banned: bool) -> str:
    if auto_banned:
        return screen(
            "⛔ Аккаунт заблокирован",
            intro="Вы получили третье предупреждение.",
            sections=("Доступ к боту ограничен бессрочно.",),
            footer="Для уточнения причины обратитесь в поддержку.",
        )
    return screen(
        "⚠️ Предупреждение",
        intro=f"Администрация выдала предупреждение {count} из 3.",
        footer="Повторные нарушения могут привести к блокировке.",
    )


def warning_admin_result(count: int, *, auto_banned: bool) -> str:
    if auto_banned:
        return "Третье предупреждение выдано. Пользователь заблокирован."
    return f"Предупреждение {count} из 3 выдано."


@router.callback_query(F.data.startswith("warn_"))
async def warn_user_unified(callback: CallbackQuery) -> None:
    if callback.from_user.id not in ADMIN_IDS:
        return

    target_id = int(callback.data.split("_")[1])
    warns_count, auto_banned = await db.warn_user(target_id)
    await db.log_action(
        target_id,
        "admin:warn",
        f"admin_id={callback.from_user.id}; count={warns_count}; source=admin_card",
    )

    try:
        await callback.bot.send_message(
            target_id,
            warning_notice(warns_count, auto_banned=auto_banned),
            parse_mode="HTML",
        )
    except Exception:
        logger.exception(
            "Не удалось уведомить пользователя о предупреждении: target_id=%s",
            target_id,
        )

    result = warning_admin_result(warns_count, auto_banned=auto_banned)
    await callback.answer(result, show_alert=True)

    from .callbacks_admin import refresh_admin_user_message

    await refresh_admin_user_message(
        callback.message,
        target_id,
        f"✅ {result}",
    )
