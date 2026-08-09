from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from aiogram.types import CallbackQuery

logger = logging.getLogger(__name__)

MessageText = str | Callable[[], str]


def _resolve_text(value: MessageText) -> str:
    return value() if callable(value) else value


async def run_state_action(
    callback: CallbackQuery,
    *,
    action: Callable[[], Awaitable[bool]],
    render: Callable[[], Awaitable[None]],
    success_text: MessageText,
    noop_text: MessageText,
    error_text: MessageText,
    on_success: Callable[[], Awaitable[None]] | None = None,
) -> bool:
    """Run one state-changing callback with a deterministic UI lifecycle.

    Sequence: action -> optional telemetry -> best-effort callback answer ->
    state reload/render. A callback-answer, rendering, or telemetry failure never
    changes the committed action result and never prevents the render attempt.

    Message arguments may be callables so an action can expose values such as a
    granted reward or affected-row count without splitting the lifecycle.
    """
    succeeded = False
    answer_text = noop_text
    show_alert = True

    try:
        succeeded = bool(await action())
    except Exception:
        logger.exception("state action failed callback=%s user_id=%s", callback.data, callback.from_user.id)
        answer_text = error_text
    else:
        if succeeded:
            answer_text = success_text
            show_alert = False
            if on_success is not None:
                try:
                    await on_success()
                except Exception:
                    logger.exception(
                        "state action telemetry failed callback=%s user_id=%s",
                        callback.data,
                        callback.from_user.id,
                    )

    try:
        await callback.answer(_resolve_text(answer_text), show_alert=show_alert)
    except Exception:
        logger.exception(
            "state action callback answer failed callback=%s user_id=%s",
            callback.data,
            callback.from_user.id,
        )

    try:
        await render()
    except Exception:
        logger.exception("state action render failed callback=%s user_id=%s", callback.data, callback.from_user.id)

    return succeeded
