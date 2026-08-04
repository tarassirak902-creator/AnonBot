from types import SimpleNamespace

import pytest

from app.services.question_handler_bridge import (
    QuestionModuleRuntime,
    initialize_question_module,
)


class FakeDb:
    async def get_question_owner_by_id(self, user_id: int):
        return (user_id,) if user_id == 2 else None

    async def get_question_by_public_id(self, public_id: str):
        return (1, public_id, 1, 2) if public_id == "q1" else None


class FakeButton:
    def __init__(self, *, text: str, callback_data: str) -> None:
        self.text = text
        self.callback_data = callback_data


class FakeMarkup:
    def __init__(self, *, inline_keyboard) -> None:
        self.inline_keyboard = inline_keyboard


def make_module():
    return SimpleNamespace(
        db=FakeDb(),
        PAGE_SIZE=7,
        InlineKeyboardButton=FakeButton,
        InlineKeyboardMarkup=FakeMarkup,
    )


def test_initializer_is_idempotent_and_preserves_context() -> None:
    module = make_module()

    first = initialize_question_module(module)
    module._question_start_targets[10] = ("token", 2, "Owner")
    second = initialize_question_module(module)

    assert isinstance(first, QuestionModuleRuntime)
    assert second is first
    assert module._question_runtime is first
    assert module._question_start_targets[10] == ("token", 2, "Owner")
    assert module.PAGE_SIZE == 7


@pytest.mark.asyncio
async def test_runtime_resolver_remains_installed() -> None:
    module = make_module()
    runtime = initialize_question_module(module)

    assert await runtime.receiver_resolver.resolve(1, "t", "2") == 2
    assert await module._resolve_question_receiver(2, "q", "q1") == 1


def test_runtime_installs_presentation_adapters() -> None:
    module = make_module()
    initialize_question_module(module)

    keyboard = module._questions_list_inline([
        (3, "public", "new", "2026-08-04T16:00:00"),
    ])

    assert keyboard.inline_keyboard[0][0].callback_data == "questions:view:public"
    assert "Вопрос №3" in keyboard.inline_keyboard[0][0].text
