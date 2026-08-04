from __future__ import annotations

from html import escape
from typing import Iterable


def screen(title: str, *sections: str, hint: str | None = None) -> str:
    """Render a compact CASPER screen with one consistent visual rhythm."""
    blocks = [f"<b>{escape(title)}</b>"]
    blocks.extend(section.strip() for section in sections if section and section.strip())
    if hint:
        blocks.append(f"<i>{escape(hint)}</i>")
    return "\n\n".join(blocks)


def status(kind: str, title: str, detail: str | None = None) -> str:
    icons = {
        "success": "✅",
        "error": "❌",
        "warning": "⚠️",
        "info": "ℹ️",
        "waiting": "⏳",
    }
    icon = icons.get(kind, "ℹ️")
    body = f"{icon} <b>{escape(title)}</b>"
    if detail:
        body += f"\n{escape(detail)}"
    return body


def metrics(items: Iterable[tuple[str, object]]) -> str:
    return "\n".join(f"{escape(label)}: <b>{escape(str(value))}</b>" for label, value in items)


def confirm(title: str, detail: str, *, danger: bool = False) -> str:
    icon = "⚠️" if danger else "❓"
    return screen(f"{icon} {title}", escape(detail), hint="Подтвердите действие кнопкой ниже.")
