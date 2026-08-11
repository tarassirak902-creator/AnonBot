from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_manual_dialog_end_creates_tokenized_rating_pair() -> None:
    source = read("app/handlers/dialog_ui.py")
    assert "create_rating_pair" in source
    assert "send_rating_prompt" in source
    assert "build_dialog_key" in source
    assert '"dialog_complete"' in source


def test_timeout_dialog_end_uses_same_feedback_pipeline() -> None:
    source = read("app/handlers/inactivity_timer_safety.py")
    assert "create_rating_pair" in source
    assert "send_rating_prompt" in source
    assert "build_dialog_key" in source
    assert '"dialog_complete"' in source


def test_legacy_partner_id_rating_is_a_tombstone_only() -> None:
    source = read("app/handlers/social_features_ui.py")
    handler = source.split('F.data.startswith("rate_partner:")', 1)[1]
    assert "db.rate_user" not in handler
    assert "db.add_xp" not in handler
    assert "устарела" in handler


def test_current_rating_route_is_single_use_and_dialog_scoped() -> None:
    source = read("app/handlers/platform_automation_ui.py")
    assert "consume_rating_token(token, callback.from_user.id)" in source
    assert "pending.dialog_key" in source
    assert "record_match_quality_rating" in source
