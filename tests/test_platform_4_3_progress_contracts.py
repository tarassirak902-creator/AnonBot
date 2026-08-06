from pathlib import Path


def test_progress_handler_is_registered_before_legacy_callbacks() -> None:
    source = Path("app/handlers/__init__.py").read_text(encoding="utf-8")
    progress_pos = source.index("from . import platform_progress_ui")
    legacy_pos = source.index("from . import callbacks_profile")
    assert progress_pos < legacy_pos


def test_growth_center_exposes_progress_and_admin_metrics() -> None:
    source = Path("app/handlers/platform_growth_ui.py").read_text(encoding="utf-8")
    assert 'callback_data="progress_center"' in source
    assert 'callback_data="admin_progress_metrics"' in source


def test_xp_ledger_is_atomic_and_idempotent() -> None:
    source = Path("app/database/platform_progress_repository.py").read_text(encoding="utf-8")
    assert "BEGIN IMMEDIATE" in source
    assert "UNIQUE(user_id, source_key)" in source
    assert "INSERT OR IGNORE INTO xp_ledger" in source
    assert "reward_claimed=0" in source


def test_weekly_progress_is_capped_and_reward_is_one_time() -> None:
    source = Path("app/database/platform_progress_repository.py").read_text(encoding="utf-8")
    assert "MIN(?, weekly_progress.progress+excluded.progress)" in source
    assert "progress>=? AND reward_claimed=0" in source
    assert "WEEKLY_TARGET = 7" in source


def test_progress_ui_does_not_log_private_message_content() -> None:
    source = Path("app/handlers/platform_progress_ui.py").read_text(encoding="utf-8")
    assert "message.text" not in source
    assert "message.caption" not in source
    assert "record_product_event" in source
