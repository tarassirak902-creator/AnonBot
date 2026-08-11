from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.handlers import ui_route_repairs


@pytest.mark.asyncio
async def test_inline_start_search_uses_callback_user_not_bot(monkeypatch) -> None:
    start_searching = AsyncMock()
    monkeypatch.setattr(ui_route_repairs, "start_searching", start_searching)

    message = SimpleNamespace(
        from_user=SimpleNamespace(id=999999),
        answer=AsyncMock(),
        delete=AsyncMock(),
        edit_reply_markup=AsyncMock(),
    )
    callback = SimpleNamespace(
        from_user=SimpleNamespace(id=12345),
        bot=object(),
        message=message,
        answer=AsyncMock(),
    )
    state = SimpleNamespace(clear=AsyncMock())

    await ui_route_repairs.start_search_from_inline(callback, state)

    state.clear.assert_awaited_once()
    callback.answer.assert_awaited_once()
    start_searching.assert_awaited_once()
    adapter = start_searching.await_args.args[0]
    assert adapter.from_user.id == 12345
    assert adapter.from_user.id != message.from_user.id
    assert adapter.answer is message.answer


@pytest.mark.asyncio
async def test_admin_broadcast_inline_entry_sets_composer_state(monkeypatch) -> None:
    monkeypatch.setattr(ui_route_repairs, "ADMIN_IDS", {12345})

    message = SimpleNamespace(
        edit_text=AsyncMock(),
        answer=AsyncMock(),
    )
    callback = SimpleNamespace(
        from_user=SimpleNamespace(id=12345),
        message=message,
        answer=AsyncMock(),
    )
    state = SimpleNamespace(
        clear=AsyncMock(),
        set_state=AsyncMock(),
    )

    await ui_route_repairs.admin_broadcast_entry(callback, state)

    state.clear.assert_awaited_once()
    state.set_state.assert_awaited_once_with(ui_route_repairs.Broadcast.waiting_for_message)
    callback.answer.assert_awaited_once()
    message.edit_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_admin_broadcast_inline_entry_rejects_non_admin(monkeypatch) -> None:
    monkeypatch.setattr(ui_route_repairs, "ADMIN_IDS", {12345})
    callback = SimpleNamespace(
        from_user=SimpleNamespace(id=67890),
        message=SimpleNamespace(edit_text=AsyncMock(), answer=AsyncMock()),
        answer=AsyncMock(),
    )
    state = SimpleNamespace(clear=AsyncMock(), set_state=AsyncMock())

    await ui_route_repairs.admin_broadcast_entry(callback, state)

    callback.answer.assert_awaited_once_with("Недостаточно прав", show_alert=True)
    state.clear.assert_not_awaited()
    state.set_state.assert_not_awaited()
