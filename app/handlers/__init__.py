# Import order matters: specific FSM/callback handlers must be registered before generic chat handlers.
from .shared import router, reset_inactivity_timer, cancel_search_timer
from . import questions
from app.services.question_handler_bridge import initialize_question_module

# Install typed service dependencies once. The initializer is idempotent, so
# module reloads do not discard short-lived personal-link context.
initialize_question_module(questions)

from . import commands
from . import service_menu
from . import forms
from . import admin_commands
from . import casper_game
from . import menus
from . import callbacks_profile
from . import referrals
from . import callbacks_duels
from . import callbacks_gifts
from . import callbacks_broadcast
from . import callbacks_admin
from . import question_subscription_gate
from . import advertising
# Must be registered before payments.py, whose legacy pre-checkout handler accepts all invoices.
from . import payment_guard
# Specific successful-payment handlers must precede the generic payment handler.
from . import duel_creation_payments
from . import duel_payments
from . import atomic_question_payments
from . import atomic_commerce_payments
from . import premium_payments
from . import payments
from . import chat

__all__ = ["router", "reset_inactivity_timer", "cancel_search_timer"]
