from __future__ import annotations

from html import escape

from app.core.ui_copy import screen


def status(kind: str, title: str, detail: str | None = None) -> str:
    """Render one canonical success/error/warning/info/waiting message."""
    icons = {
        "success": "✅",
        "error": "❌",
        "warning": "⚠️",
        "info": "ℹ️",
        "waiting": "⏳",
    }
    icon = icons.get(kind, "ℹ️")
    sections = (escape(detail),) if detail else ()
    return screen(f"{icon} {title}", sections=sections)


def confirm(title: str, detail: str, *, danger: bool = False) -> str:
    """Render a consistent confirmation prompt for normal and dangerous actions."""
    icon = "⚠️" if danger else "❓"
    return screen(
        f"{icon} {title}",
        intro=detail,
        footer="Подтвердите действие кнопкой ниже.",
    )
