from __future__ import annotations

from app.database.product_analytics_repository import record_product_event_safe

from . import shared


_installed = False


def install_product_event_hooks() -> None:
    """Instrument the canonical search function before handlers copy it from shared."""
    global _installed
    if _installed:
        return
    _installed = True
    original_start_searching = shared.start_searching

    async def instrumented_start_searching(message):
        user_id = message.from_user.id
        if await shared.db.get_partner(user_id):
            return await original_start_searching(message)

        await record_product_event_safe(user_id, "search_started")
        await original_start_searching(message)

        partner_id = await shared.db.get_partner(user_id)
        if partner_id:
            await record_product_event_safe(user_id, "match_found")
            await record_product_event_safe(partner_id, "match_found")

    shared.start_searching = instrumented_start_searching
