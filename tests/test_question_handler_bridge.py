from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.question_handler_bridge import install_question_services


class FakeDb:
    def __init__(self) -> None:
        self.owners = {20: (20,)}
        self.questions = {
            "q1": (1, "q1", 10, 20),
        }

    async def get_question_owner_by_id(self, user_id: int):
        return self.owners.get(user_id)

    async def get_question_by_public_id(self, public_id: str):
        return self.questions.get(public_id)


@pytest.mark.asyncio
async def test_bridge_installs_tuple_compatible_bounded_store() -> None:
    module = SimpleNamespace(db=FakeDb(), _question_start_targets={}, _resolve_question_receiver=None)
    install_question_services(module, max_start_contexts=2, start_context_ttl_seconds=60)

    module._question_start_targets[1] = ("token", 20, "Alice")

    assert module._question_start_targets.get(1) == ("token", 20, "Alice")
    assert module._question_start_targets.pop(1) == ("token", 20, "Alice")
    assert module._question_start_targets.get(1) is None


@pytest.mark.asyncio
async def test_bridge_replaces_legacy_receiver_resolver() -> None:
    module = SimpleNamespace(db=FakeDb(), _question_start_targets={}, _resolve_question_receiver=None)
    install_question_services(module)

    assert await module._resolve_question_receiver(10, "t", "20") == 20
    assert await module._resolve_question_receiver(20, "q", "q1") == 10
    assert await module._resolve_question_receiver(10, "a", "q1") == 20
    assert await module._resolve_question_receiver(20, "a", "q1") is None
