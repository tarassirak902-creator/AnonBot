from __future__ import annotations

import aiosqlite
import pytest

from app.services import profile_insights


@pytest.mark.asyncio
async def test_profile_insights_use_real_user_and_purchase_columns(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "profile-insights.db")
    monkeypatch.setattr(profile_insights, "DB_PATH", db_path)

    async with aiosqlite.connect(db_path) as conn:
        await conn.executescript(
            """
            CREATE TABLE users (
                user_id INTEGER PRIMARY KEY,
                completed_dialogs INTEGER DEFAULT 0,
                referred_by INTEGER
            );
            CREATE TABLE anonymous_questions (
                sender_id INTEGER,
                receiver_id INTEGER,
                status TEXT
            );
            CREATE TABLE question_link_visits (owner_id INTEGER);
            CREATE TABLE purchases (
                buyer_id INTEGER,
                receiver_id INTEGER,
                type TEXT
            );
            """
        )
        await conn.executemany(
            "INSERT INTO users(user_id,completed_dialogs,referred_by) VALUES (?,?,?)",
            [(1, 7, None), (2, 1, 1), (3, 0, 1)],
        )
        await conn.executemany(
            "INSERT INTO purchases(buyer_id,receiver_id,type) VALUES (?,?,?)",
            [(1, 2, "gift"), (1, 3, "question_gift"), (2, 1, "question_gift")],
        )
        await conn.commit()

    result = await profile_insights.load_profile_insights(1)

    assert result.completed_chats == 7
    assert result.referrals_total == 2
    assert result.gifts_sent == 2
    assert result.gifts_received == 1
