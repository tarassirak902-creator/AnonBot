from app.core.ui_labels import ButtonText, ScreenTitle


def test_navigation_labels_are_canonical() -> None:
    assert ButtonText.BACK == "⬅️ Назад"
    assert ButtonText.HOME == "🏠 Главное меню"
    assert ButtonText.CANCEL == "❌ Отмена"
    assert ButtonText.REFRESH == "🔄 Обновить"


def test_common_action_labels_are_short() -> None:
    labels = [
        ButtonText.BACK,
        ButtonText.HOME,
        ButtonText.CANCEL,
        ButtonText.CLOSE,
        ButtonText.CONFIRM,
        ButtonText.REFRESH,
        ButtonText.DETAILS,
    ]
    assert all(len(label) <= 24 for label in labels)


def test_screen_titles_do_not_use_caps_lock() -> None:
    titles = [
        ScreenTitle.MAIN_MENU,
        ScreenTitle.PROFILE,
        ScreenTitle.ACHIEVEMENTS,
        ScreenTitle.QUESTIONS,
        ScreenTitle.ADMIN,
        ScreenTitle.PAYMENT,
        ScreenTitle.WITHDRAW,
    ]
    assert all(title != title.upper() for title in titles)
