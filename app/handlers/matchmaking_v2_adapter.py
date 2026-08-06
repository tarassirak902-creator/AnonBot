from __future__ import annotations

from app.services.matchmaking_service import enqueue_or_match, leave_queue

from . import shared


async def _try_match_user(user_id: int) -> int | None:
    result = await enqueue_or_match(user_id)
    if result.recovered_rows:
        await shared.db.log_action(
            user_id,
            "matchmaking_recovered",
            f"rows={result.recovered_rows}",
        )
    return result.partner_id


async def _remove_from_queue(user_id: int) -> None:
    await leave_queue(user_id)


def install_matchmaking_v2() -> None:
    """Route legacy matchmaking calls through the recovery-aware service."""
    shared.db.try_match_user = _try_match_user
    shared.db.remove_from_queue = _remove_from_queue
