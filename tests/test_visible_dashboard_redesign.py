from pathlib import Path


def test_profile_is_action_first_dashboard() -> None:
    profile = Path("app/handlers/profile_view.py").read_text(encoding="utf-8")
    hub = Path("app/handlers/profile_action_entry.py").read_text(encoding="utf-8")
    assert "👤 Мой профиль" in profile
    assert "⚡ Активность" in profile
    assert "🎁 Награды" in profile
    assert "🤝 Социальное" in profile
    assert "👑 Премиум" in profile
    assert "🏆 Мои достижения" in hub
    assert "⭐ Баланс" in hub
    assert "🏠 На главную" in profile


def test_questions_home_has_prominent_actions() -> None:
    source = Path("app/handlers/question_browser_ui.py").read_text(encoding="utf-8")
    assert "📥 Открыть входящие вопросы" in source
    assert "💬 Посмотреть полученные ответы" in source
    assert "🔗 Поделиться моей ссылкой" in source
    assert "questions.questions_home_inline = questions_home_inline" in source


def test_admin_panel_accepts_new_and_legacy_labels() -> None:
    source = Path("app/handlers/admin_overview_ui.py").read_text(encoding="utf-8")
    assert "⚙️ Панель управления" in source
    assert "⚙️ Админ-панель CASPER" in source
    assert "🔧 Админ-панель" in source
    assert "📥 Скачать базу пользователей" in source


def test_redesign_preserves_callback_contracts() -> None:
    source = Path("app/handlers/question_browser_ui.py").read_text(encoding="utf-8")
    for callback in (
        "questions:mine",
        "questions:answers",
        "questions:link",
        "questions:reply",
        "questions:gift",
        "questions:buy_reveal",
    ):
        assert callback in source
