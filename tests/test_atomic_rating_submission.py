import aiosqlite
import pytest

from app.database import platform_automation_repository as ratings


@pytest.mark.asyncio
async def test_rating_submission_consumes_token_and_persists_once(tmp_path, monkeypatch):
    db_path = tmp_path / "ratings.db"
    monkeypatch.setattr(ratings, "DB_PATH", str(db_path))

    first, _second = await ratings.create_rating_pair(101, 202, dialog_key="101:202:test")
    saved = await ratings.consume_rating_and_save(first.token, 101, 1)

    assert saved is not None
    assert saved.rater_id == 101
    assert saved.rated_user_id == 202
    assert await ratings.consume_rating_and_save(first.token, 101, -1) is None

    async with aiosqlite.connect(db_path) as db:
        row = await (await db.execute(
            "SELECT rater_id, rated_user_id, dialog_key, rating FROM dialog_ratings"
        )).fetchone()
        token_row = await (await db.execute(
            "SELECT consumed_at FROM pending_dialog_ratings WHERE token=?",
            (first.token,),
        )).fetchone()

    assert row == (101, 202, "101:202:test", 1)
    assert token_row is not None and token_row[0] is not None


@pytest.mark.asyncio
async def test_invalid_rating_does_not_consume_token(tmp_path, monkeypatch):
    db_path = tmp_path / "ratings.db"
    monkeypatch.setattr(ratings, "DB_PATH", str(db_path))

    first, _second = await ratings.create_rating_pair(303, 404, dialog_key="303:404:test")
    assert await ratings.consume_rating_and_save(first.token, 303, 99) is None

    valid = await ratings.consume_rating_and_save(first.token, 303, 0)
    assert valid is not None
