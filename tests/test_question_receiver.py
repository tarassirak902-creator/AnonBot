from __future__ import annotations

import pytest

from app.services.question_receiver import QuestionReceiverResolver


class FakeRepository:
    def __init__(self) -> None:
        self.owners = {10: object(), 20: object(), 30: object()}
        self.questions = {
            "q1": (1, "q1", 10, 20),
            "self": (2, "self", 10, 10),
            "broken": (3, "broken", "bad", 20),
        }

    async def get_owner_by_id(self, user_id: int):
        return self.owners.get(user_id)

    async def get_question(self, public_id: str):
        return self.questions.get(public_id)


def resolver(repo: FakeRepository) -> QuestionReceiverResolver:
    return QuestionReceiverResolver(
        get_owner_by_id=repo.get_owner_by_id,
        get_question_by_public_id=repo.get_question,
    )


@pytest.mark.asyncio
async def test_direct_context_requires_existing_other_user() -> None:
    repo = FakeRepository()
    service = resolver(repo)

    assert await service.resolve(10, "t", "20") == 20
    assert await service.resolve(10, "t", "10") is None
    assert await service.resolve(10, "t", "999") is None
    assert await service.resolve(10, "t", "not-a-number") is None


@pytest.mark.asyncio
async def test_question_receiver_can_send_back_to_sender() -> None:
    repo = FakeRepository()
    service = resolver(repo)

    assert await service.resolve(20, "q", "q1") == 10
    assert await service.resolve(10, "q", "q1") is None


@pytest.mark.asyncio
async def test_question_sender_can_send_to_answering_user() -> None:
    repo = FakeRepository()
    service = resolver(repo)

    assert await service.resolve(10, "a", "q1") == 20
    assert await service.resolve(20, "a", "q1") is None


@pytest.mark.asyncio
async def test_invalid_context_and_malformed_rows_are_rejected() -> None:
    repo = FakeRepository()
    service = resolver(repo)

    assert await service.resolve(10, "unknown", "q1") is None
    assert await service.resolve(10, "a", "missing") is None
    assert await service.resolve(20, "q", "broken") is None
    assert await service.resolve(10, "a", "self") is None
