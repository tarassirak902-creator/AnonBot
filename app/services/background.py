from __future__ import annotations

import asyncio
import logging
from datetime import datetime

import aiosqlite
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app import database as db
from app.core import texts
from app.services.matchmaking_service import recover_matchmaking_state

logger = logging.getLogger(__name__)


def get_reminder_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💬 Найти собеседника",
                    callback_data="reminder_find_partner",
                )
            ]
        ]
    )


async def vip_expiration_checker_loop(bot: Bot) -> None:
    """Проверяет истёкшие VIP-подписки один раз в час."""
    while True:
        try:
            async with aiosqlite.connect(db.DB_PATH) as connection:
                cursor = await connection.execute(
                    "SELECT user_id, vip_expires_at FROM users WHERE is_vip = 1"
                )
                rows = await cursor.fetchall()
                now = datetime.now()

                for user_id, expires_at in rows:
                    if not expires_at:
                        continue
                    try:
                        expiration = datetime.fromisoformat(expires_at)
                    except (ValueError, TypeError):
                        logger.warning("Некорректная дата VIP пользователя %s", user_id)
                        continue

                    if now < expiration:
                        continue

                    await connection.execute(
                        "UPDATE users SET is_vip = 0, vip_expires_at = NULL WHERE user_id = ?",
                        (user_id,),
                    )
                    await connection.commit()

                    try:
                        keyboard = InlineKeyboardMarkup(
                            inline_keyboard=[
                                [
                                    InlineKeyboardButton(
                                        text="👑 Продлить VIP (100 ⭐)",
                                        callback_data="buy_vip_sub",
                                    )
                                ]
                            ]
                        )
                        await bot.send_message(
                            user_id,
                            "⚠️ <b>Срок вашей VIP подписки истёк!</b>\n\n"
                            "Действие скидки 30% на подарки и защиты от "
                            "авто-ограничений приостановлено. Вы можете "
                            "продлить подписку в профиле.",
                            parse_mode="HTML",
                            reply_markup=keyboard,
                        )
                    except Exception:
                        logger.exception(
                            "Не удалось уведомить пользователя %s об окончании VIP",
                            user_id,
                        )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Ошибка проверки VIP-подписок")

        await asyncio.sleep(3600)


async def auto_reminder_loop(bot: Bot) -> None:
    """Отправляет напоминания давно неактивным пользователям."""
    while True:
        try:
            await asyncio.sleep(43200)
            inactive_users = await db.get_inactive_users()

            for user_id in inactive_users:
                try:
                    await bot.send_message(
                        chat_id=user_id,
                        text=texts.get_random_message(),
                        parse_mode="Markdown",
                        reply_markup=get_reminder_keyboard(),
                    )
                    await asyncio.sleep(0.1)
                except TelegramRetryAfter as error:
                    logger.warning(
                        "Лимит Telegram: ожидание %s секунд", error.retry_after
                    )
                    await asyncio.sleep(error.retry_after)
                except TelegramForbiddenError as error:
                    await db.log_action(
                        user_id,
                        "reminder_unreachable",
                        str(error),
                    )
                except Exception:
                    logger.exception(
                        "Не удалось отправить напоминание пользователю %s",
                        user_id,
                    )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Ошибка цикла авто-напоминаний")
            await asyncio.sleep(60)


async def referral_reward_loop(bot: Bot) -> None:
    """Начисляет награду после пяти завершённых диалогов приглашённого."""
    while True:
        try:
            eligible = await db.get_eligible_referrals(required_dialogs=5)
            for invited_id, referrer_id in eligible:
                reward_stars = 50
                claimed = await db.claim_referral_reward(
                    invited_id, referrer_id, reward_stars
                )
                if not claimed:
                    continue
                try:
                    await bot.send_message(
                        referrer_id,
                        "🎉 <b>Ваш друг стал активным пользователем CASPER GO!</b>\n\n"
                        f"За приглашение начислено: <b>+{reward_stars} виртуальных ⭐</b>.\n"
                        "Награда уже добавлена на внутренний баланс.",
                        parse_mode="HTML",
                    )
                except Exception:
                    logger.exception("Не удалось уведомить реферера %s", referrer_id)
                try:
                    await bot.send_message(
                        invited_id,
                        "🎉 <b>Вы стали активным пользователем CASPER GO!</b>\n\n"
                        "Вашему другу начислена награда за приглашение. Спасибо, что вы с нами 💜",
                        parse_mode="HTML",
                    )
                except Exception:
                    logger.exception("Не удалось уведомить приглашённого %s", invited_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Ошибка обработки реферальных наград")

        await asyncio.sleep(300)


async def temporary_mute_expiration_loop(bot: Bot) -> None:
    """Снимает истёкшие временные муты и уведомляет пользователя."""
    while True:
        try:
            now = datetime.now().isoformat()
            async with aiosqlite.connect(db.DB_PATH, timeout=10) as connection:
                await connection.execute("BEGIN IMMEDIATE")
                rows = await (await connection.execute(
                    "SELECT user_id FROM users WHERE blocked=1 AND blocked_until IS NOT NULL AND blocked_until<=?",
                    (now,),
                )).fetchall()
                ids = [row[0] for row in rows]
                if ids:
                    await connection.executemany(
                        "UPDATE users SET blocked=0,blocked_until=NULL WHERE user_id=? AND blocked=1",
                        [(uid,) for uid in ids],
                    )
                await connection.commit()
            for uid in ids:
                try:
                    kb = InlineKeyboardMarkup(inline_keyboard=[[
                        InlineKeyboardButton(text="▶️ Старт", callback_data="restriction_removed_start")
                    ]])
                    await bot.send_message(
                        uid,
                        "✅ <b>Срок временного ограничения закончился.</b>\n\n"
                        "Вы снова можете пользоваться ботом.",
                        parse_mode="HTML",
                        reply_markup=kb,
                    )
                except Exception:
                    logger.exception("Не удалось уведомить пользователя %s о снятии мута", uid)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Ошибка проверки временных мутов")
        await asyncio.sleep(60)


async def matchmaking_recovery_loop() -> None:
    """Periodically repairs only transient matchmaking state."""
    while True:
        try:
            repaired = await recover_matchmaking_state()
            if repaired:
                logger.warning("Автовосстановление матчинга исправило строк: %s", repaired)
                try:
                    await db.log_action(0, "matchmaking_auto_recovery", f"rows={repaired}")
                except Exception:
                    logger.exception("Не удалось записать recovery-событие")
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Ошибка автоматического восстановления матчинга")
        await asyncio.sleep(60)


def create_background_tasks(bot: Bot) -> list[asyncio.Task]:
    return [
        asyncio.create_task(auto_reminder_loop(bot), name="auto_reminder"),
        asyncio.create_task(referral_reward_loop(bot), name="referral_reward"),
        asyncio.create_task(vip_expiration_checker_loop(bot), name="vip_expiration"),
        asyncio.create_task(temporary_mute_expiration_loop(bot), name="temporary_mute_expiration"),
        asyncio.create_task(matchmaking_recovery_loop(), name="matchmaking_recovery"),
    ]


async def stop_background_tasks(tasks: list[asyncio.Task]) -> None:
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
