from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import aiosqlite

from .repository import DB_PATH


@dataclass(frozen=True)
class ReferralActivation:
    inviter_id: int
    invited_id: int
    activated: bool
    reward_claimed: bool


@dataclass(frozen=True)
class ReferralSummary:
    registered: int
    activated: int
    rewarded: int
    pending_rewards: int


async def _ensure_schema(db: aiosqlite.Connection) -> None:
    await db.executescript(
        """
        CREATE TABLE IF NOT EXISTS referral_activations (
            invited_id INTEGER PRIMARY KEY,
            inviter_id INTEGER NOT NULL,
            activated_at TEXT,
            reward_claimed INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CHECK(inviter_id <> invited_id)
        );
        CREATE INDEX IF NOT EXISTS idx_referral_activations_inviter
            ON referral_activations(inviter_id, activated_at);
        """
    )


async def register_referral(inviter_id: int, invited_id: int) -> bool:
    if inviter_id <= 0 or invited_id <= 0 or inviter_id == invited_id:
        return False
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        await _ensure_schema(db)
        await db.execute("BEGIN IMMEDIATE")
        cur = await db.execute(
            "INSERT OR IGNORE INTO referral_activations(invited_id, inviter_id) VALUES (?, ?)",
            (invited_id, inviter_id),
        )
        await db.commit()
        return cur.rowcount == 1


async def activate_referral(invited_id: int, completed_dialogs: int) -> bool:
    if completed_dialogs < 5:
        return False
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        await _ensure_schema(db)
        await db.execute("BEGIN IMMEDIATE")
        cur = await db.execute(
            """UPDATE referral_activations
               SET activated_at = COALESCE(activated_at, ?)
               WHERE invited_id = ? AND activated_at IS NULL""",
            (now, invited_id),
        )
        await db.commit()
        return cur.rowcount == 1


async def claim_referral_reward(inviter_id: int, invited_id: int) -> bool:
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        await _ensure_schema(db)
        await db.execute("BEGIN IMMEDIATE")
        cur = await db.execute(
            """UPDATE referral_activations
               SET reward_claimed = 1
               WHERE inviter_id = ? AND invited_id = ?
                 AND activated_at IS NOT NULL
                 AND activated_at <= ?
                 AND reward_claimed = 0""",
            (inviter_id, invited_id, cutoff),
        )
        await db.commit()
        return cur.rowcount == 1


async def get_referral_summary(inviter_id: int) -> ReferralSummary:
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        await _ensure_schema(db)
        row = await (await db.execute(
            """SELECT
                   COUNT(*),
                   SUM(CASE WHEN activated_at IS NOT NULL THEN 1 ELSE 0 END),
                   SUM(CASE WHEN reward_claimed = 1 THEN 1 ELSE 0 END),
                   SUM(CASE WHEN activated_at IS NOT NULL AND reward_claimed = 0 THEN 1 ELSE 0 END)
               FROM referral_activations
               WHERE inviter_id = ?""",
            (inviter_id,),
        )).fetchone()
    values = row or (0, 0, 0, 0)
    return ReferralSummary(*(int(value or 0) for value in values))


async def referral_metrics() -> dict[str, int]:
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        await _ensure_schema(db)
        async def scalar(sql: str) -> int:
            row = await (await db.execute(sql)).fetchone()
            return int((row[0] if row else 0) or 0)
        return {
            "registered": await scalar("SELECT COUNT(*) FROM referral_activations"),
            "activated": await scalar("SELECT COUNT(*) FROM referral_activations WHERE activated_at IS NOT NULL"),
            "rewarded": await scalar("SELECT COUNT(*) FROM referral_activations WHERE reward_claimed = 1"),
            "suspicious": await scalar("SELECT COUNT(*) FROM referral_activations WHERE inviter_id = invited_id"),
        }
