from __future__ import annotations

from html import escape

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.core.ui_copy import screen


def confirmation_screen(title: str, detail: str, *, danger: bool = False) -> str:
    icon = "⚠️" if danger else "❓"
    return screen(
        f"{icon} {title}",
        intro=detail,
        footer="Подтвердите действие кнопкой ниже.",
    )


def confirmation_keyboard(
    confirm_text: str,
    confirm_callback: str,
    cancel_callback: str,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=confirm_text, callback_data=confirm_callback),
            InlineKeyboardButton(text="❌ Отмена", callback_data=cancel_callback),
        ]
    ])


def payment_description(product: str, benefit: str, period: str | None = None) -> str:
    parts = [product]
    if period:
        parts.append(period)
    parts.append(benefit)
    return ". ".join(escape(part).strip(". ") for part in parts if part) + "."


def withdraw_screen(balance: int) -> str:
    return screen(
        "💸 Вывод звёзд",
        sections=(
            f"⭐ Доступно: <b>{int(balance)} ⭐</b>",
            "Введите сумму, которую хотите вывести.",
        ),
        footer="Сумма не может превышать доступный баланс.",
    )
