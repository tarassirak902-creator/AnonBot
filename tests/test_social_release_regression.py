from pathlib import Path


INIT = Path("app/handlers/__init__.py").read_text(encoding="utf-8")
PROFILE_GAMES = Path("app/handlers/profile_games_ui.py").read_text(encoding="utf-8")
PROFILE = Path("app/handlers/profile_view.py").read_text(encoding="utf-8")
MATCHMAKING = Path("app/database/matchmaking_repository.py").read_text(encoding="utf-8")
SCHEMA = Path("app/database/schema_migrations.py").read_text(encoding="utf-8")


def test_profile_keyboard_compat_is_installed_before_profile_games() -> None:
    assert "install_keyboard_compat()" in INIT
    assert INIT.index("install_keyboard_compat()") < INIT.index("from . import profile_games_ui")
    assert "await hide_reply_keyboard(message)" in PROFILE_GAMES


def test_profile_contains_social_progress_and_daily_reward() -> None:
    assert 'callback_data="profile_daily_reward"' in PROFILE
    assert 'reputation = await db.get_reputation(user_id)' in PROFILE
    assert 'metric("⚡", "Уровень"' in PROFILE
    assert 'metric("✨", "XP"' in PROFILE
    assert 'metric("⭐", "Репутация"' in PROFILE


def test_matchmaking_deprioritizes_recent_partners_without_blocking_fallback() -> None:
    assert "recent_partners rp" in MATCHMAKING
    assert "datetime('now','-30 minutes')" in MATCHMAKING
    assert "THEN 1 ELSE 0 END" in MATCHMAKING
    assert "ON CONFLICT(user_id,partner_id) DO UPDATE" in MATCHMAKING


def test_social_schema_tables_are_migrated() -> None:
    for table in ("chat_ratings", "recent_partners", "daily_rewards", "user_progress"):
        assert table in SCHEMA
