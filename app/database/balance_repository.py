from __future__ import annotations

import aiosqlite

from .repository import DB_PATH


async def deduct_user_balance(user_id: int, amount: int) -> bool:
    """Atomically deduct a positive amount without allowing the balance below zero."""
    try:
        safe_user_id = int(user_id)
        safe_amount = int(amount)
    except (TypeError, ValueError):
        return False
    if safe_user_id < 1 or safe_amount < 1:
        return False

    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        await conn.execute("PRAGMA busy_timeout=10000")
        cursor = await conn.execute(
            "UPDATE users "
            "SET stars_balance=COALESCE(stars_balance,0)-? "
            "WHERE user_id=? AND COALESCE(stars_balance,0)>=?",
            (safe_amount, safe_user_id, safe_amount),
        )
        await conn.commit()
        return cursor.rowcount == 1
