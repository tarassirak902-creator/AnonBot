from __future__ import annotations

from app.database.product_analytics_repository import record_product_event_safe
from app.services.matchmaking_service import enqueue_or_match, leave_queue

from . import product_analytics_ui  # register admin funnel callback early
from . import shared

_original_log_action = shared.db.log_action


async def _log_action(user_id: int, action: str, details: str = ""):
    result = await _original_log_action(user_id, action, details)
    event = {
        "start": "app_start",
        "queue_timeout": "search_timeout",
        "queue_leave": "search_cancelled",
    }.get(action)
    if event:
        await record_product_event_safe(user_id, event)
    return result


async def _try_match_user(user_id: int) -> int | None:
    await record_product_event_safe(user_id, "search_started")
    result = await enqueue_or_match(user_id)
    if result.recovered_rows:
        await shared.db.log_action(
            user_id,
            "matchmaking_recovered",
            f"rows={result.recovered_rows}",
        )
    if result.partner_id:
        await record_product_event_safe(user_id, "match_found")
        await record_product_event_safe(result.partner_id, "match_found")
    return result.partner_id


async def _remove_from_queue(user_id: int) -> None:
    await leave_queue(user_id)


def install_matchmaking_v2() -> None:
    """Route legacy matchmaking calls through the recovery-aware service."""
    shared.db.try_match_user = _try_match_user
    shared.db.remove_from_queue = _remove_from_queue
    shared.db.log_action = _log_action
