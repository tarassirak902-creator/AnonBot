from pathlib import Path


def test_platform_4_2_handlers_are_registered_before_legacy_callbacks() -> None:
    source = Path("app/handlers/__init__.py").read_text(encoding="utf-8")
    referral_pos = source.index("from . import platform_referral_ui")
    shop_pos = source.index("from . import platform_shop_ui")
    legacy_pos = source.index("from . import callbacks_profile")
    assert referral_pos < legacy_pos
    assert shop_pos < legacy_pos


def test_growth_center_uses_platform_4_2_routes() -> None:
    source = Path("app/handlers/platform_growth_ui.py").read_text(encoding="utf-8")
    assert 'callback_data="platform_referrals"' in source
    assert 'callback_data="platform_shop"' in source
    assert 'callback_data="profile_shop"' not in source


def test_referral_repository_blocks_self_referrals_and_duplicate_rewards() -> None:
    source = Path("app/database/platform_referral_repository.py").read_text(encoding="utf-8")
    assert "inviter_id == invited_id" in source
    assert "BEGIN IMMEDIATE" in source
    assert "reward_claimed = 0" in source
    assert "get_referral_summary" in source


def test_shop_categories_use_cooldowns_and_safe_routes() -> None:
    source = Path("app/handlers/platform_shop_ui.py").read_text(encoding="utf-8")
    assert "acquire_action_slot" in source
    assert 'F.data.startswith("shop_category:")' in source
    assert "platform_shop" in source
