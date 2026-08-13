from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import aiosqlite

from .repository import DB_PATH


@dataclass(frozen=True)
class ManualChatEnd:
    partner_id: int
    user_duration_seconds: int
    partner_duration_seconds: int
    user_completed: bool
    partner_completed: bool


def _elapsed_seconds(start_raw: str | None, now: datetime) -> int:
    if not start_raw:
        return 0
    try:
        start = datetime.fromisoformat(str(start_raw))
        current = now if start.tzinfo is None else datetime.now(start.tzinfo)
        return max(0, int((current - start).total_seconds()))
    except (TypeError, ValueError, OverflowError):
        return 0


async def end_chat_with_accounting(
    user_id: int,
    *,
    min_completed_seconds: int = 60,
) -> ManualChatEnd | None:
    """Account both participants and tear down one manual dialog atomically."""
    try:
        user_id = int(user_id)
        min_completed_seconds = max(0, int(min_completed_seconds))
    except (TypeError, ValueError):
        return None
    if user_id <= 0:
        return None

    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        await conn.execute("PRAGMA busy_timeout=10000")
        await conn.execute("BEGIN IMMEDIATE")
        try:
            row = await (await conn.execute(
                "SELECT partner_id FROM active_chats WHERE user_id=?",
                (user_id,),
            )).fetchone()
            if not row:
                await conn.execute("DELETE FROM queues WHERE user_id=?", (user_id,))
                await conn.execute(
                    "UPDATE users SET current_chat_start=NULL WHERE user_id=?",
                    (user_id,),
                )
                await conn.commit()
                return None

            partner_id = int(row[0])
            starts = await (await conn.execute(
                "SELECT user_id,current_chat_start FROM users WHERE user_id IN (?,?)",
                (user_id, partner_id),
            )).fetchall()
            start_by_user = {int(item[0]): item[1] for item in starts}
            now = datetime.now()
            now_iso = now.isoformat()
            user_duration = _elapsed_seconds(start_by_user.get(user_id), now)
            partner_duration = _elapsed_seconds(start_by_user.get(partner_id), now)

            for uid, duration in ((user_id, user_duration), (partner_id, partner_duration)):
                await conn.execute(
                    """UPDATE users
                       SET chat_time_seconds=COALESCE(chat_time_seconds,0)+?,
                           completed_dialogs=COALESCE(completed_dialogs,0)+CASE WHEN ?>=? THEN 1 ELSE 0 END,
                           current_chat_start=NULL,
                           last_activity=?
                     WHERE user_id=?""",
                    (duration, duration, min_completed_seconds, now_iso, uid),
                )

            await conn.execute(
                "DELETE FROM active_chats WHERE user_id IN (?,?) OR partner_id IN (?,?)",
                (user_id, partner_id, user_id, partner_id),
            )
            await conn.execute(
                "DELETE FROM queues WHERE user_id IN (?,?)",
                (user_id, partner_id),
            )
            await conn.commit()
            return ManualChatEnd(
                partner_id=partner_id,
                user_duration_seconds=user_duration,
                partner_duration_seconds=partner_duration,
                user_completed=user_duration >= min_completed_seconds,
                partner_completed=partner_duration >= min_completed_seconds,
            )
        except Exception:
            await conn.rollback()
            raise
