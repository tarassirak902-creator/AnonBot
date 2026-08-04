from app.handlers.admin_results_ui import normalize_admin_result


def test_normalizes_vip_results() -> None:
    assert normalize_admin_result("✅ VIP выдан") == "✅ VIP активирован"
    assert normalize_admin_result("VIP снят") == "✅ VIP отключён"


def test_normalizes_restriction_results() -> None:
    assert normalize_admin_result("✅ Мут на 24 часа выдан") == "✅ Ограничение на 24 часа включено"
    assert normalize_admin_result("Пользователь разблокирован") == "✅ Ограничение снято"
    assert normalize_admin_result("Пользователь забанен") == "✅ Бессрочная блокировка включена"


def test_normalizes_warning_results() -> None:
    assert normalize_admin_result("✅ Выдано предупреждение #2 из 3") == "✅ предупреждение #2 из 3"
    assert normalize_admin_result("⛔ Выдано третье предупреждение — пользователь автоматически заблокирован") == "⛔ Третье предупреждение: аккаунт заблокирован"


def test_removes_legacy_exclamation_marks() -> None:
    assert normalize_admin_result("✅ Действие выполнено!") == "✅ Изменения сохранены"
