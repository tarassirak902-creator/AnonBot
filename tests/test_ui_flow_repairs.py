from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.handlers import advertising_entry_ui, duel_action_ui, duel_entry_ui


@pytest.mark.asyncio
async def test_duel_decline_rejects_non_partner(monkeypatch) -> None:
    duel = (77, 10, 20, 50, "waiting", "darts")
    monkeypatch.setattr(duel_action_ui.db, "get_game_duel", AsyncMock(return_value=duel))
    update = AsyncMock()
    monkeypatch.setattr(duel_action_ui.db, "update_game_duel_status", update)

    callback = SimpleNamespace(
        data="decline_duel_77",
        from_user=SimpleNamespace(id=30),
        answer=AsyncMock(),
        message=SimpleNamespace(delete=AsyncMock(), edit_reply_markup=AsyncMock()),
        bot=SimpleNamespace(send_message=AsyncMock()),
    )

    await duel_action_ui.decline_duel(callback)

    callback.answer.assert_awaited_once_with(
        "Этот вызов предназначен другому пользователю.",
        show_alert=True,
    )
    update.assert_not_awaited()


@pytest.mark.asyncio
async def test_duel_accept_rejects_non_partner(monkeypatch) -> None:
    duel = (77, 10, 20, 50, "waiting", "darts")
    monkeypatch.setattr(duel_action_ui.db, "get_game_duel", AsyncMock(return_value=duel))
    callback = SimpleNamespace(
        data="pay_duel_accept_77",
        from_user=SimpleNamespace(id=30),
        answer=AsyncMock(),
        message=SimpleNamespace(answer_invoice=AsyncMock()),
    )

    await duel_action_ui.accept_duel_invoice(callback)

    callback.answer.assert_awaited_once_with(
        "Этот вызов предназначен другому пользователю.",
        show_alert=True,
    )
    callback.message.answer_invoice.assert_not_awaited()


def test_duel_prompt_matches_actual_ninety_percent_payout() -> None:
    text = duel_entry_ui._duel_bet_prompt("Дартс")
    assert "90% общего банка" in text
    assert "весь банк" not in text
    assert "При ничьей обе ставки возвращаются" in text


@pytest.mark.asyncio
async def test_advertising_instruction_uses_runtime_bot_username(monkeypatch) -> None:
    callback = SimpleNamespace(
        data="ads_community_channel",
        bot=SimpleNamespace(get_me=AsyncMock(return_value=SimpleNamespace(username="real_casper_bot"))),
        message=SimpleNamespace(delete=AsyncMock(), answer=AsyncMock()),
        answer=AsyncMock(),
    )
    state = SimpleNamespace(update_data=AsyncMock(), set_state=AsyncMock())

    await advertising_entry_ui.ads_choose_community_type_entry(callback, state)

    text = callback.message.answer.await_args.args[0]
    assert "@real_casper_bot" in text
    assert "@anonchatvoice_bot" not in text
    state.set_state.assert_awaited_once_with("AdOrder:waiting_channel")
