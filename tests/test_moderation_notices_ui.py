from app.handlers.moderation_notices_ui import (
    restriction_details_keyboard,
    restriction_notice,
    restriction_removed_keyboard,
    restriction_removed_notice,
    warning_notice,
)


def test_restriction_notices_use_consistent_titles() -> None:
    temporary = restriction_notice(permanent=False)
    permanent = restriction_notice(permanent=True)

    assert "🔇 Доступ временно ограничен" in temporary
    assert "⛔ Доступ ограничен" in permanent
    assert "Подробнее" in temporary
    assert "Подробнее" in permanent


def test_warning_notice_covers_regular_and_auto_ban_states() -> None:
    regular = warning_notice(2)
    banned = warning_notice(3, auto_banned=True)

    assert "2 из 3" in regular
    assert "третье предупреждение" in banned


def test_moderation_keyboards_keep_callback_contracts() -> None:
    details = restriction_details_keyboard().inline_keyboard
    removed = restriction_removed_keyboard().inline_keyboard

    assert details[0][0].callback_data == "is_banned_alert"
    assert removed[0][0].callback_data == "restriction_removed_start"


def test_removed_notice_is_short_and_actionable() -> None:
    text = restriction_removed_notice()

    assert "✅ Ограничение снято" in text
    assert "снова можете пользоваться ботом" in text
