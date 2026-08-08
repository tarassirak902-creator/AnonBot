from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core.action_flow import run_state_action


class FakeCallback:
    def __init__(self) -> None:
        self.data = "test_action"
        self.from_user = SimpleNamespace(id=101)
        self.answers: list[tuple[str, bool]] = []

    async def answer(self, text: str, *, show_alert: bool = False) -> None:
        self.answers.append((text, show_alert))


@pytest.mark.asyncio
async def test_state_action_success_answers_once_and_renders() -> None:
    callback = FakeCallback()
    events: list[str] = []

    async def action() -> bool:
        events.append("action")
        return True

    async def telemetry() -> None:
        events.append("telemetry")

    async def render() -> None:
        events.append("render")

    result = await run_state_action(
        callback,
        action=action,
        render=render,
        success_text="ok",
        noop_text="noop",
        error_text="error",
        on_success=telemetry,
    )

    assert result is True
    assert callback.answers == [("ok", False)]
    assert events == ["action", "telemetry", "render"]


@pytest.mark.asyncio
async def test_state_action_noop_answers_once_and_renders() -> None:
    callback = FakeCallback()
    rendered = 0

    async def action() -> bool:
        return False

    async def render() -> None:
        nonlocal rendered
        rendered += 1

    result = await run_state_action(
        callback,
        action=action,
        render=render,
        success_text="ok",
        noop_text="already",
        error_text="error",
    )

    assert result is False
    assert callback.answers == [("already", True)]
    assert rendered == 1


@pytest.mark.asyncio
async def test_state_action_failure_answers_once_and_still_renders() -> None:
    callback = FakeCallback()
    rendered = 0

    async def action() -> bool:
        raise RuntimeError("boom")

    async def render() -> None:
        nonlocal rendered
        rendered += 1

    result = await run_state_action(
        callback,
        action=action,
        render=render,
        success_text="ok",
        noop_text="noop",
        error_text="failed",
    )

    assert result is False
    assert callback.answers == [("failed", True)]
    assert rendered == 1


@pytest.mark.asyncio
async def test_state_action_telemetry_failure_does_not_change_success() -> None:
    callback = FakeCallback()
    rendered = 0

    async def action() -> bool:
        return True

    async def telemetry() -> None:
        raise RuntimeError("metrics unavailable")

    async def render() -> None:
        nonlocal rendered
        rendered += 1

    result = await run_state_action(
        callback,
        action=action,
        render=render,
        success_text="done",
        noop_text="noop",
        error_text="failed",
        on_success=telemetry,
    )

    assert result is True
    assert callback.answers == [("done", False)]
    assert rendered == 1
