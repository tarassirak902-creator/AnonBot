from pathlib import Path


ALIASES = Path("app/handlers/visible_button_aliases.py").read_text(encoding="utf-8")


CANONICAL_LABELS = {
    "💬 Найти собеседника",
    "❌  Отменить поиск",
    "➡️ Новый собеседник",
    "➡️ Следующий собеседник",
    "⏹ Завершить",
    "❌ Завершить диалог",
    "🎮 Мини-игры",
    "Мини игры",
    "👤 Моя анкета",
    "⚙️ Профиль",
    "🎁 Пригласить друга",
    "👥 Пригласить друга",
    "🔗 Пригласить друга",
    "⚔️ Играть с собеседником",
    "🎁 Подарить подарок",
    "⭐ Кто собеседник",
    "⚠️ Пожаловаться",
}


def test_visible_alias_router_does_not_reregister_canonical_labels() -> None:
    for label in CANONICAL_LABELS:
        assert label not in ALIASES, f"Canonical label leaked back into alias router: {label}"


def test_alias_router_documents_import_order_risk() -> None:
    assert "duplicate aiogram routes depend on import order" in ALIASES
