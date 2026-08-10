from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

from app import database as db

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PaymentReconciliationRequired:
    """Handler result used when money was received but the business action failed."""

    reason: str


def payment_reconciliation_required(reason: str) -> PaymentReconciliationRequired:
    """Return a bounded reconciliation result for a successful-payment handler."""
    safe_reason = (reason or "payment business action was not completed").strip()[:1000]
    return PaymentReconciliationRequired(safe_reason)


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
                "charge_id=%s user_id=%s payment_type=%s",
                charge_id,
                event.from_user.id,
                (payment.invoice_payload or "unknown").split(":", 1)[0].split("_", 1)[0][:48],
            )
            return None

        try:
            result = await handler(event, data)
        except Exception as exc:
            await db.release_payment_processing(charge_id, repr(exc))
            logger.exception(
                "Payment handler failed; charge retained for manual reconciliation: "
                "charge_id=%s user_id=%s",
                charge_id,
                event.from_user.id,
            )
            raise

        if isinstance(result, PaymentReconciliationRequired):
            await db.release_payment_processing(charge_id, result.reason)
            logger.error(
                "Payment business action incomplete; charge retained for reconciliation: "
                "charge_id=%s user_id=%s reason=%s",
                charge_id,
                event.from_user.id,
                result.reason,
            )
            return None

        await db.complete_payment_processing(charge_id)
        return result
