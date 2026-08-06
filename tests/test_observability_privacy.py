from pathlib import Path


def test_observability_never_logs_message_payload() -> None:
    source = Path("app/core/middlewares.py").read_text(encoding="utf-8")

    assert "text[:80]" not in source
    assert "event.text or event.caption" not in source
    assert "message:{content_type}:len=" in source
    assert "payload = event.text if event.text is not None else event.caption" in source


def test_callback_logging_is_bounded_and_does_not_expand_payload() -> None:
    source = Path("app/core/middlewares.py").read_text(encoding="utf-8")

    assert ".split(\":\", 1)[0][:64]" in source
    assert "callback:{callback_name}" in source
