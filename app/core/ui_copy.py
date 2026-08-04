from __future__ import annotations

from collections.abc import Iterable
from html import escape

DIVIDER = "───────────────"


def screen(title: str, *, intro: str | None = None, sections: Iterable[str] = (), footer: str | None = None) -> str:
    """Build a consistent compact HTML screen used by user and admin flows."""
    parts = [f"<b>{escape(title)}</b>"]
    if intro:
        parts.append(escape(intro))
    parts.extend(section for section in sections if section)
    if footer:
        parts.append(f"<i>{escape(footer)}</i>")
    return "\n\n".join(parts)


def section(title: str, rows: Iterable[str]) -> str:
    body = "\n".join(row for row in rows if row)
    return f"<b>{escape(title)}</b>\n{body}" if body else f"<b>{escape(title)}</b>"


def metric(icon: str, label: str, value: object) -> str:
    return f"{icon} {escape(label)}: <b>{escape(str(value))}</b>"


def status_text(kind: str, text: str) -> str:
    icons = {"success": "✅", "warning": "⚠️", "error": "❌", "info": "ℹ️"}
    return f"{icons.get(kind, 'ℹ️')} <b>{escape(text)}</b>"
