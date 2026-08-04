from __future__ import annotations


def normalize_admin_result(prefix: str | None) -> str | None:
    """Normalize legacy moderation result banners shown above user cards."""
    if not prefix:
        return None

    value = prefix.strip()
    lowered = value.lower()

    if "vip" in lowered:
        if any(token in lowered for token in ("снят", "отмен", "удал")):
            return "✅ VIP отключён"
        return "✅ VIP активирован"

    if "мут" in lowered or "24 час" in lowered:
        return "✅ Ограничение на 24 часа включено"

    if "разблок" in lowered or "ограничение снято" in lowered:
        return "✅ Ограничение снято"

    if "заблок" in lowered or "бан" in lowered:
        return "✅ Бессрочная блокировка включена"

    if "предупрежден" in lowered:
        if "автомат" in lowered or "треть" in lowered:
            return "⛔ Третье предупреждение: аккаунт заблокирован"
        return value.replace("Выдано ", "").replace("!", "")

    if "действие выполнено" in lowered:
        return "✅ Изменения сохранены"

    return value.rstrip("!")


def install_admin_result_ui() -> None:
    """Patch only the presentation boundary after callbacks_admin is loaded."""
    from . import callbacks_admin

    original = callbacks_admin.refresh_admin_user_message

    async def refresh_admin_user_message(message, user_id: int, prefix: str | None = None):
        return await original(message, user_id, normalize_admin_result(prefix))

    callbacks_admin.refresh_admin_user_message = refresh_admin_user_message
