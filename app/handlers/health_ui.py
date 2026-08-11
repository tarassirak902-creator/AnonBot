from __future__ import annotations

from aiogram.filters import Command
from aiogram.types import Message

from app.services.health_service import collect_health_checks, format_health_report
from .shared import ADMIN_IDS, router


@router.message(Command("health"))
async def admin_health_command(message: Message) -> None:
    if message.from_user.id not in ADMIN_IDS:
        return
    checks = await collect_health_checks(message.bot)
    await message.answer(format_health_report(checks), parse_mode="HTML")
