from pathlib import Path


DELIVERY_UI = Path("app/handlers/question_delivery_ui.py").read_text(encoding="utf-8")
HANDLERS_INIT = Path("app/handlers/__init__.py").read_text(encoding="utf-8")


def test_question_delivery_handlers_are_replaced() -> None:
    assert '_replace_message_handler("save_question", save_question_ui)' in DELIVERY_UI
    assert '_replace_message_handler("send_answer", send_answer_ui)' in DELIVERY_UI
    assert "install_question_delivery_ui()" in HANDLERS_INIT


def test_question_delivery_keeps_business_contracts() -> None:
    assert "create_anonymous_question" in DELIVERY_UI
    assert "answer_question" in DELIVERY_UI
    assert '"question_sent"' in DELIVERY_UI
    assert '"question_answered"' in DELIVERY_UI
    assert "set_question_chat_pending" in DELIVERY_UI
    assert "set_answer_chat_pending" in DELIVERY_UI


def test_question_delivery_uses_unified_states() -> None:
    expected = (
        "⚠️ Проверьте вопрос",
        "⚠️ Проверьте ответ",
        "✅ Вопрос отправлен",
        "✅ Ответ отправлен",
        "❌ Получатель недоступен",
        "❌ Вопрос недоступен",
        "❓ Новый анонимный вопрос",
        "💬 Получен ответ",
    )
    for text in expected:
        assert text in DELIVERY_UI


def test_question_delivery_preserves_limits_and_anonymity() -> None:
    assert "len(text) > 1500" in DELIVERY_UI
    assert "len(answer_text) > 1500" in DELIVERY_UI
    assert "без вашего имени" in DELIVERY_UI
