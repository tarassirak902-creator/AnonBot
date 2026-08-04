from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

from app import database as db

logger = logging.getLogger(__name__)


class PaymentIdempotencyMiddleware(BaseMiddleware):
    """Prevents duplicate side effects for repeated successful-payment updates.

    A Telegram charge is claimed before dispatching handlers. Once claimed, it is
    never automatically made retryable: after a crash we cannot know whether a
    gift, balance credit or subscription was already applied. Failed attempts are
    retained in the ledger for support reconciliation.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        if not isinstance(event, Message) or event.successful_payment is None:
            return await handler(event, data)

        payment = event.successful_payment
        charge_id = payment.telegram_payment_charge_id
        claimed = await db.claim_payment_processing(
            charge_id,
            event.from_user.id,
            payment.invoice_payload,
            int(payment.total_amount),
        )
        if not claimed:
            logger.warning(
                "Duplicate, interrupted or conflicting payment update ignored: "
                "charge_id=%s user_id=%s payload=%s",
                charge_id,
                event.from_user.id,
                payment.invoice_payload,
            )
            return None

        try:
            result = await handler(event, data)
        except Exception as exc:
            await db.release_payment_processing(charge_id, repr(exc))
            logger.exception(
                "Payment handler failed; charge retained for manual reconciliation: "
                "charge_id=%s user_id=%s payload=%s",
                charge_id,
                event.from_user.id,
                payment.invoice_payload,
            )
            raise
        else:
            await db.complete_payment_processing(charge_id)
            return result
