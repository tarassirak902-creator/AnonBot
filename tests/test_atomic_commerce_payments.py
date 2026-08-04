from types import SimpleNamespace

import pytest

from app.handlers import atomic_commerce_payments


@pytest.mark.asyncio
async def test_paid_author_reveal_escapes_telegram_profile_html(monkeypatch) -> None:
    async def apply_question_reveal_payment(**kwargs):
        return 42

    monkeypatch.setattr(
        atomic_commerce_payments.db,
        "apply_question_reveal_payment",
        apply_question_reveal_payment,
    )

    answers: list[tuple[str, str | None]] = []

    class FakeBot:
        async def get_chat(self, user_id: int):
            assert user_id == 42
            return SimpleNamespace(
                id=42,
                first_name="<b>Alice</b>",
                last_name="& Bob",
                username="name<unsafe>",
            )

    async def answer(text: str, parse_mode: str | None = None):
        answers.append((text, parse_mode))

    message = SimpleNamespace(
        successful_payment=SimpleNamespace(
            invoice_payload="question_reveal:public-id",
            telegram_payment_charge_id="charge-1",
            total_amount=100,
        ),
        from_user=SimpleNamespace(id=7),
        bot=FakeBot(),
        answer=answer,
    )

    await atomic_commerce_payments.successful_question_reveal_payment(message)

    assert len(answers) == 1
    text, parse_mode = answers[0]
    assert parse_mode == "HTML"
    assert "&lt;b&gt;Alice&lt;/b&gt; &amp; Bob" in text
    assert "@name&lt;unsafe&gt;" in text
    assert "<b>Alice</b>" not in text
