from __future__ import annotations

from datetime import datetime, timedelta

import aiosqlite

from .repository import DB_PATH


async def _ensure_payment_schema(conn: aiosqlite.Connection) -> None:
    columns = await (await conn.execute("PRAGMA table_info(purchases)")).fetchall()
    if "telegram_payment_charge_id" not in {row[1] for row in columns}:
        await conn.execute(
            "ALTER TABLE purchases ADD COLUMN telegram_payment_charge_id TEXT"
        )
    await conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_purchases_charge_id "
        "ON purchases(telegram_payment_charge_id) "
        "WHERE telegram_payment_charge_id IS NOT NULL"
    )


async def _charge_already_applied(
    conn: aiosqlite.Connection,
    charge_id: str,
) -> bool:
    row = await (
        await conn.execute(
            "SELECT 1 FROM purchases WHERE telegram_payment_charge_id=?",
            (charge_id,),
        )
    ).fetchone()
    return row is not None


async def _require_users(
    conn: aiosqlite.Connection,
    *user_ids: int,
) -> None:
    for user_id in set(user_ids):
        row = await (
            await conn.execute("SELECT 1 FROM users WHERE user_id=?", (user_id,))
        ).fetchone()
        if not row:
            raise ValueError(f"user does not exist: {user_id}")


async def apply_question_stars_payment(
    *,
    charge_id: str,
    buyer_id: int,
    receiver_id: int,
    amount: int,
) -> bool:
    """Atomically credit question Stars and persist purchase/statistics."""
    if not charge_id or buyer_id == receiver_id or amount < 1:
        raise ValueError("invalid question Stars payment")

    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        await conn.execute("PRAGMA busy_timeout=10000")
        await conn.execute("BEGIN IMMEDIATE")
        await _ensure_payment_schema(conn)
        if await _charge_already_applied(conn, charge_id):
            await conn.rollback()
            return False
        await _require_users(conn, buyer_id, receiver_id)

        await conn.execute(
            "UPDATE users SET stars_balance=COALESCE(stars_balance,0)+? WHERE user_id=?",
            (amount, receiver_id),
        )
        await conn.execute(
            "UPDATE users SET total_stars_spent=COALESCE(total_stars_spent,0)+? WHERE user_id=?",
            (amount, buyer_id),
        )
        await conn.execute(
            "INSERT INTO purchases "
            "(buyer_id,receiver_id,gift_id,price_stars,type,timestamp,telegram_payment_charge_id) "
            "VALUES (?,?,?,?,?,?,?)",
            (buyer_id, receiver_id, 0, amount, "question_stars", now, charge_id),
        )
        await conn.execute(
            "INSERT INTO logs(user_id,action,details,timestamp) VALUES (?,?,?,?)",
            (
                buyer_id,
                "question_stars_sent",
                f"receiver_id={receiver_id}; stars={amount}; charge_id={charge_id}",
                now,
            ),
        )
        await conn.commit()
        return True


async def apply_vip_payment(
    *,
    charge_id: str,
    buyer_id: int,
    receiver_id: int,
    amount: int,
    days: int,
    purchase_type: str,
) -> bool:
    """Atomically extend VIP, record spending and persist the purchase."""
    if not charge_id or amount < 1 or days < 1:
        raise ValueError("invalid VIP payment")
    if purchase_type not in {"question_vip", "vip_subscription"}:
        raise ValueError("unsupported VIP purchase type")

    now = datetime.now()
    now_iso = now.isoformat()
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        await conn.execute("PRAGMA busy_timeout=10000")
        await conn.execute("BEGIN IMMEDIATE")
        await _ensure_payment_schema(conn)
        if await _charge_already_applied(conn, charge_id):
            await conn.rollback()
            return False
        await _require_users(conn, buyer_id, receiver_id)

        receiver = await (
            await conn.execute(
                "SELECT vip_expires_at FROM users WHERE user_id=?", (receiver_id,)
            )
        ).fetchone()
        base = now
        if receiver and receiver[0]:
            try:
                current = datetime.fromisoformat(receiver[0])
                if current > now:
                    base = current
            except (TypeError, ValueError):
                pass
        expires = (base + timedelta(days=days)).isoformat()

        await conn.execute(
            "UPDATE users SET is_vip=1,vip_expires_at=? WHERE user_id=?",
            (expires, receiver_id),
        )
        await conn.execute(
            "UPDATE users SET total_stars_spent=COALESCE(total_stars_spent,0)+? WHERE user_id=?",
            (amount, buyer_id),
        )
        await conn.execute(
            "INSERT INTO purchases "
            "(buyer_id,receiver_id,gift_id,price_stars,type,timestamp,telegram_payment_charge_id) "
            "VALUES (?,?,?,?,?,?,?)",
            (buyer_id, receiver_id, 0, amount, purchase_type, now_iso, charge_id),
        )
        action = "question_vip_sent" if purchase_type == "question_vip" else "vip_activated"
        await conn.execute(
            "INSERT INTO logs(user_id,action,details,timestamp) VALUES (?,?,?,?)",
            (
                buyer_id,
                action,
                f"receiver_id={receiver_id}; days={days}; stars={amount}; charge_id={charge_id}",
                now_iso,
            ),
        )
        await conn.commit()
        return True


async def apply_gift_payment(
    *,
    charge_id: str,
    buyer_id: int,
    receiver_id: int,
    gift_id: int,
    amount: int,
    purchase_type: str,
) -> bool:
    """Atomically record a paid gift and update both users' counters."""
    if not charge_id or buyer_id == receiver_id or gift_id < 1 or amount < 1:
        raise ValueError("invalid gift payment")
    if purchase_type not in {"gift", "question_gift"}:
        raise ValueError("unsupported gift purchase type")

    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        await conn.execute("PRAGMA busy_timeout=10000")
        await conn.execute("BEGIN IMMEDIATE")
        await _ensure_payment_schema(conn)
        if await _charge_already_applied(conn, charge_id):
            await conn.rollback()
            return False
        await _require_users(conn, buyer_id, receiver_id)

        gift = await (
            await conn.execute("SELECT 1 FROM gifts WHERE id=?", (gift_id,))
        ).fetchone()
        if not gift:
            await conn.rollback()
            raise ValueError("gift does not exist")

        await conn.execute(
            "UPDATE users SET sent_gifts=COALESCE(sent_gifts,0)+1, "
            "total_stars_spent=COALESCE(total_stars_spent,0)+? WHERE user_id=?",
            (amount, buyer_id),
        )
        await conn.execute(
            "UPDATE users SET received_gifts=COALESCE(received_gifts,0)+1 WHERE user_id=?",
            (receiver_id,),
        )
        await conn.execute(
            "INSERT INTO purchases "
            "(buyer_id,receiver_id,gift_id,price_stars,type,timestamp,telegram_payment_charge_id) "
            "VALUES (?,?,?,?,?,?,?)",
            (buyer_id, receiver_id, gift_id, amount, purchase_type, now, charge_id),
        )
        await conn.execute(
            "INSERT INTO logs(user_id,action,details,timestamp) VALUES (?,?,?,?)",
            (
                buyer_id,
                "question_gift_sent" if purchase_type == "question_gift" else "gift_sent",
                f"receiver_id={receiver_id}; gift_id={gift_id}; stars={amount}; charge_id={charge_id}",
                now,
            ),
        )
        await conn.commit()
        return True


async def apply_question_reveal_payment(
    *,
    charge_id: str,
    buyer_id: int,
    public_id: str,
    amount: int,
) -> int | None:
    """Atomically reveal a question author and record the purchase.

    Returns the sender ID, or ``None`` when the same Telegram charge was already
    applied. A question already revealed by another charge is rejected.
    """
    if not charge_id or not public_id or amount < 1:
        raise ValueError("invalid question reveal payment")

    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        await conn.execute("PRAGMA busy_timeout=10000")
        await conn.execute("BEGIN IMMEDIATE")
        await _ensure_payment_schema(conn)
        if await _charge_already_applied(conn, charge_id):
            await conn.rollback()
            return None

        question = await (
            await conn.execute(
                "SELECT sender_id,receiver_id,author_revealed "
                "FROM anonymous_questions WHERE public_id=?",
                (public_id,),
            )
        ).fetchone()
        if not question or int(question[1]) != int(buyer_id):
            await conn.rollback()
            raise ValueError("question does not belong to buyer")
        if bool(question[2]):
            await conn.rollback()
            raise ValueError("question author already revealed")

        sender_id = int(question[0])
        await _require_users(conn, buyer_id, sender_id)
        cursor = await conn.execute(
            "UPDATE anonymous_questions SET author_revealed=1 "
            "WHERE public_id=? AND receiver_id=? AND author_revealed=0",
            (public_id, buyer_id),
        )
        if cursor.rowcount != 1:
            await conn.rollback()
            raise ValueError("question reveal race detected")

        await conn.execute(
            "UPDATE users SET total_stars_spent=COALESCE(total_stars_spent,0)+? WHERE user_id=?",
            (amount, buyer_id),
        )
        await conn.execute(
            "INSERT INTO purchases "
            "(buyer_id,receiver_id,gift_id,price_stars,type,timestamp,telegram_payment_charge_id) "
            "VALUES (?,?,?,?,?,?,?)",
            (buyer_id, sender_id, 0, amount, "question_reveal", now, charge_id),
        )
        await conn.execute(
            "INSERT INTO logs(user_id,action,details,timestamp) VALUES (?,?,?,?)",
            (
                buyer_id,
                "question_reveal_sent",
                f"public_id={public_id}; sender_id={sender_id}; stars={amount}; charge_id={charge_id}",
                now,
            ),
        )
        await conn.commit()
        return sender_id
