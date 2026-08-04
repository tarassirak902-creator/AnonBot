from app.handlers.admin_warning_ui import warning_admin_result, warning_notice


def test_warning_notice_uses_consistent_screen_copy() -> None:
    text = warning_notice(2, auto_banned=False)
    assert "⚠️ <b>Предупреждение</b>" in text
    assert "2 из 3" in text
    assert "Повторные нарушения" in text


def test_third_warning_mentions_permanent_block() -> None:
    text = warning_notice(3, auto_banned=True)
    assert "⛔ <b>Аккаунт заблокирован</b>" in text
    assert "третье предупреждение" in text.lower()
    assert "бессрочно" in text.lower()


def test_admin_results_are_short_and_without_exclamation_noise() -> None:
    regular = warning_admin_result(1, auto_banned=False)
    blocked = warning_admin_result(3, auto_banned=True)
    assert regular == "Предупреждение 1 из 3 выдано."
    assert blocked == "Третье предупреждение выдано. Пользователь заблокирован."
    assert "!" not in regular + blocked
