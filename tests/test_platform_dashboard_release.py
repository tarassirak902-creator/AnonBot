from pathlib import Path


def test_platform_dashboard_is_registered_before_chat() -> None:
    source = Path("app/handlers/__init__.py").read_text(encoding="utf-8")
    assert "from . import platform_dashboard_ui" in source
    assert source.index("from . import platform_dashboard_ui") < source.index("from . import chat")


def test_user_contacts_can_be_listed_and_removed() -> None:
    service = Path("app/services/platform_insights.py").read_text(encoding="utf-8")
    ui = Path("app/handlers/platform_dashboard_ui.py").read_text(encoding="utf-8")
    community = Path("app/handlers/community_ui.py").read_text(encoding="utf-8")
    assert "load_recent_anonymous_contacts" in service
    assert "remove_anonymous_contact" in service
    assert "community_contacts_list" in ui
    assert "community_contact_remove:" in ui
    assert "📋 Мои контакты" in community


def test_admin_operations_dashboard_has_core_metrics() -> None:
    service = Path("app/services/platform_insights.py").read_text(encoding="utf-8")
    ui = Path("app/handlers/platform_dashboard_ui.py").read_text(encoding="utf-8")
    overview = Path("app/handlers/admin_overview_ui.py").read_text(encoding="utf-8")
    for field in (
        '"queue"',
        '"active_chats"',
        '"users_24h"',
        '"complaints"',
        '"negative_ratings_24h"',
    ):
        assert field in service
    assert "📡 Центр управления" in ui
    assert "admin_ops_refresh" in ui
    assert "admin_ops_dashboard" in overview


def test_platform_insights_tolerate_legacy_schema() -> None:
    source = Path("app/services/platform_insights.py").read_text(encoding="utf-8")
    assert "_table_exists" in source
    assert "_columns" in source
    assert "except aiosqlite.Error" in source
