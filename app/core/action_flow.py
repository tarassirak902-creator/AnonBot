from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from aiogram.types import CallbackQuery

logger = logging.getLogger(__name__)


async def run_state_action(
    callback: CallbackQuery,
    *,
    action: Callable[[], Awaitable[bool]],
    render: Callable[[], Awaitable[None]],
    success_text: str,
    noop_text: str,
    error_text: str,
    on_success: Callable[[], Awaitable[None]] | None = None,
) -> bool:
    """Run one state-changing callback with a deterministic UI lifecycle.

    Sequence: action -> optional telemetry -> exactly one callback answer ->
    state reload/render. A rendering or telemetry failure never causes a second
    callback answer and never changes the committed action result.
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

    await callback.answer(answer_text, show_alert=show_alert)

    try:
        await render()
    except Exception:
        logger.exception("state action render failed callback=%s user_id=%s", callback.data, callback.from_user.id)

    return succeeded
