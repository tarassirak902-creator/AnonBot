from pathlib import Path


def test_profile_has_safe_social_fallback() -> None:
    source = Path("app/handlers/profile_view.py").read_text(encoding="utf-8")
    assert "_safe_reputation" in source
    assert "DEFAULT_REPUTATION" in source
    assert "_safe_int" in source
    assert "🏠 На главную" in source


def test_community_repository_has_preferences_and_mutual_reconnect() -> None:
    source = Path("app/database/community_repository.py").read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS user_preferences" in source
    assert "CREATE TABLE IF NOT EXISTS reconnect_requests" in source
    assert "async def set_user_preferences" in source
    assert "async def request_reconnect" in source
    assert 'return "matched"' in source
