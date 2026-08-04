from pathlib import Path


def test_profile_has_safe_social_fallback() -> None:
    source = Path("app/handlers/profile_view.py").read_text(encoding="utf-8")
    assert "_safe_reputation" in source
    assert "DEFAULT_REPUTATION" in source
    assert "_safe_int" in source
    assert "🏠 На главную" in source


def test_community_repository_has_mutual_reconnect_only() -> None:
    source = Path("app/database/community_repository.py").read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS reconnect_requests" in source
    assert "async def request_reconnect" in source
    assert "async def are_reconnect_matched" in source
    assert 'return "matched"' in source
    assert "user_preferences" not in source
    assert "set_user_preferences" not in source
    assert "interests_json" not in source
    assert "language TEXT" not in source
