from __future__ import annotations

from datetime import datetime

import aiosqlite

from .repository import DB_PATH


def _positive_ids_and_amount(user_id: int, amount: int) -> tuple[int, int] | None:
    try:
        safe_user_id = int(user_id)
        safe_amount = int(amount)
    except (TypeError, ValueError):
        return None
    if safe_user_id < 1 or safe_amount < 1:
        return None
    return safe_user_id, safe_amount


async def deduct_user_balance(user_id: int, amount: int) -> bool:
    """Atomically deduct a positive amount without allowing the balance below zero."""
    validated = _positive_ids_and_amount(user_id, amount)
    if validated is None:
        return False
    safe_user_id, safe_amount = validated

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


async def create_withdraw_request_atomic(user_id: int, amount: int) -> int | None:
    """Reserve a positive balance amount and create one withdrawal atomically."""
    validated = _positive_ids_and_amount(user_id, amount)
    if validated is None:
        return None
    safe_user_id, safe_amount = validated

    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        await conn.execute("PRAGMA busy_timeout=10000")
        await conn.execute("BEGIN IMMEDIATE")
        cursor = await conn.execute(
            "UPDATE users "
            "SET stars_balance=COALESCE(stars_balance,0)-? "
            "WHERE user_id=? AND COALESCE(stars_balance,0)>=?",
            (safe_amount, safe_user_id, safe_amount),
        )
        if cursor.rowcount != 1:
            await conn.rollback()
            return None
        cursor = await conn.execute(
            "INSERT INTO withdraw_requests (user_id,amount,status,timestamp) "
            "VALUES (?,?,'pending',?)",
            (safe_user_id, safe_amount, datetime.now().isoformat()),
        )
        await conn.commit()
        return int(cursor.lastrowid)


async def create_withdraw_request(user_id: int, amount: int) -> int:
    request_id = await create_withdraw_request_atomic(user_id, amount)
    if request_id is None:
        raise ValueError("Недостаточно средств или некорректная сумма")
    return request_id
