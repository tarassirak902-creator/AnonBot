from aiogram import F
from aiogram.types import CallbackQuery

from .events_audit_ui import _render_event
from .shared import router


@router.callback_query(F.data == "weekly_event")
async def weekly_event_commercial_alias(callback: CallbackQuery) -> None:
    await _render_event(callback, parent="rewards")
