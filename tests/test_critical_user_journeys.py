from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HANDLERS = ROOT / "app" / "handlers"


def _all_handler_source() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in sorted(HANDLERS.glob("*.py")))


def _assert_journey(source: str, name: str, markers: tuple[str, ...]) -> None:
    missing = [marker for marker in markers if marker not in source]
    assert not missing, f"Critical journey {name!r} lost required steps: {missing}"


def test_chat_journey_contract() -> None:
    source = _all_handler_source()
    _assert_journey(source, "chat", (
        'callback_data="start_search"',
        'F.data == "start_search"',
        '"end": "⏹ Завершить"',
        'callback_data="nav_main_menu"',
    ))


def test_profile_and_vip_journey_contract() -> None:
    source = _all_handler_source()
    _assert_journey(source, "profile-vip", (
        'callback_data="profile_refresh"',
        'callback_data="profile_hub_premium"',
        'callback_data="buy_vip_sub"',
        'payload="vip_subscription_100"',
    ))


def test_advertising_journey_contract() -> None:
    source = _all_handler_source()
    _assert_journey(source, "advertising", (
        'callback_data="ads_buy_post"',
        'callback_data="ads_submit_order"',
        'callback_data=f"ads_order_pay_',
        'payload=f"ad_order_',
    ))


def test_duel_journey_contract() -> None:
    source = _all_handler_source()
    _assert_journey(source, "duel", (
        'callback_data=f"pay_duel_accept_',
        'callback_data=f"decline_duel_',
        'invoice_payload.startswith("duel_accept_")',
        'settle_active_duel',
    ))


def test_questions_journey_contract() -> None:
    source = _all_handler_source()
    _assert_journey(source, "questions", (
        'callback_data=f"qtarget:',
        'callback_data=f"qstars:',
        'question_vip:',
        'successful_payment',
    ))
