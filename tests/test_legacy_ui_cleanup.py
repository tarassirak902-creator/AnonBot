from pathlib import Path


HANDLERS = Path("app/handlers")


def _source(name: str) -> str:
    return (HANDLERS / name).read_text(encoding="utf-8")


def test_legacy_screens_use_unified_renderer() -> None:
    for name in ("activity_health_ui.py", "engagement_ui.py", "events_audit_ui.py"):
        source = _source(name)
        assert "app.core.ui_renderer" in source
        assert "callback.message.answer(" not in source


def test_activity_and_admin_health_render_in_place() -> None:
    source = _source("activity_health_ui.py")
    assert "await render_callback(" in source
    assert 'answer_text="Обновлено"' in source
    assert "await render_message(" in source
    assert "prefer_edit=False" in source


def test_engagement_claim_answers_once_then_renders() -> None:
    source = _source("engagement_ui.py")
    handler = source.split("async def engagement_mission_claim", 1)[1].split("def _retention_keyboard", 1)[0]
    assert "await _render_missions(callback, answer_text=answer_text" in handler
    assert "await callback.answer(" not in handler


def test_weekly_claim_does_not_double_answer_callback() -> None:
    source = _source("events_audit_ui.py")
    handler = source.split("async def weekly_event_claim", 1)[1].split("async def _audit_text", 1)[0]
    assert handler.count("await callback.answer(") == 2  # early incomplete path + final result path
    assert "await _render_event(callback" not in handler
    assert "await render_message(callback.message" in handler


def test_audit_callbacks_use_unified_renderer() -> None:
    source = _source("events_audit_ui.py")
    handler = source.split("async def admin_audit_journal", 1)[1]
    assert "await render_callback(" in handler
    assert 'answer_text="Обновлено"' in handler
