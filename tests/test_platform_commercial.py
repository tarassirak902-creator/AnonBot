from pathlib import Path


def test_commercial_platform_routes_are_registered() -> None:
    init_source = Path("app/handlers/__init__.py").read_text(encoding="utf-8")
    ui_source = Path("app/handlers/platform_commercial_ui.py").read_text(encoding="utf-8")
    assert "from . import platform_commercial_ui" in init_source
    assert 'F.data == "profile_platform_status"' in ui_source
    assert '"admin_business_dashboard"' in ui_source
    assert '"admin_business_from_growth"' in ui_source


def test_profile_and_admin_expose_unified_entries() -> None:
    profile_source = Path("app/handlers/profile_view.py").read_text(encoding="utf-8")
    admin_source = Path("app/handlers/admin_overview_ui.py").read_text(encoding="utf-8")
    assert 'text="🚀 Статус"' in profile_source
    assert 'callback_data="profile_platform_status"' in profile_source
    assert 'text="💼 Бизнес"' in admin_source
    assert 'callback_data="admin_business_dashboard"' in admin_source


def test_commercial_status_uses_canonical_progress_without_message_content() -> None:
    source = Path("app/services/platform_commercial.py").read_text(encoding="utf-8")
    assert "get_progress_profile" in source
    assert "messages_count" not in source
    assert "chat_time_seconds" not in source
    assert "reconnect_requests" in source
    assert "SELECT text" not in source
    assert "message_text" not in source
    assert "purchases" in source
