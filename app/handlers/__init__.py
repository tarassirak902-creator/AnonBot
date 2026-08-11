# Import order matters: specific FSM/callback handlers must be registered before generic chat handlers.
from .shared import router, reset_inactivity_timer, cancel_search_timer
from .minimal_keyboard_ui import install_minimal_keyboards
from .keyboard_compat import install_keyboard_compat
from .matchmaking_v2_adapter import install_matchmaking_v2

# Canonical compact reply keyboards and compatibility hooks must be installed
# before modules copy names from shared.
install_minimal_keyboards()
install_keyboard_compat()
install_matchmaking_v2()

from . import questions
from app.services.question_handler_bridge import initialize_question_module
from .question_entry_ui import install_question_entry_ui
from .question_copy_ui import install_question_copy_ui
from .question_browser_ui import install_question_browser_ui
from .question_delivery_ui import install_question_delivery_ui
from .question_details_ui import install_question_details_ui
from .admin_card_ui import install_admin_card_ui

# Install UI/service boundaries before callback modules import shared symbols.
initialize_question_module(questions)
install_question_entry_ui()
install_question_copy_ui()
install_question_browser_ui()
install_question_delivery_ui()
install_question_details_ui()
install_admin_card_ui()

from . import commands
from . import service_menu
from . import forms
from . import admin_commands
from . import casper_game
# Register guaranteed profile action entry points before feature and legacy callbacks.
from . import profile_action_entry
from . import events_audit_ui
from . import navigation_integrity_ui
from . import commercial_profile_aliases
from . import commercial_navigation_ui
from . import commercial_daily_hub
from . import platform_commercial_ui
from . import platform_social_ui
from . import platform_automation_ui
from . import platform_growth_ui
from . import platform_referral_ui
from . import platform_shop_ui
from . import platform_progress_ui
from . import platform_missions_ui
from . import platform_personal_goals_ui
from . import platform_reactivation_ui
from . import platform_match_quality_ui
from . import navigation_fallback_ui
# Unified admin and user entry screens must be registered before legacy handlers.
from . import admin_overview_ui
from . import platform_dashboard_ui
from . import history_moderation_ui
from . import engagement_ui
from . import activity_health_ui
from . import admin_lists_ui
from . import admin_confirmation_ui
from . import admin_warning_ui
from . import user_actions_ui
from . import dialog_ui
from .search_ui import install_search_copy
install_search_copy()
from . import menus
from . import profile_achievements
# Payment/profile entry adapters must be registered before legacy profile callbacks.
from . import payment_entry_ui
from . import duel_entry_ui
from . import callbacks_profile
from . import referrals
from . import callbacks_duels
from . import callbacks_gifts
from . import callbacks_broadcast
from . import callbacks_admin
# Patch presentation-only moderation boundaries after the legacy module is loaded.
from .moderation_notices_ui import install_moderation_notices
from .admin_results_ui import install_admin_result_ui
install_moderation_notices()
install_admin_result_ui()
from . import question_subscription_gate
# Entry copy that depends on the runtime bot identity must register before the legacy advertising module.
from . import advertising_entry_ui
from . import advertising
from . import social_features_ui
from . import community_ui
# Register canonical and legacy reply-button aliases only after their target modules exist.
from . import visible_button_aliases
# Repair inline entry routes before generic payment/chat fallbacks.
from . import ui_route_repairs
# Must be registered before payments.py, whose legacy pre-checkout handler accepts all invoices.
from . import payment_guard
# Specific successful-payment handlers must precede the generic payment handler.
from . import duel_creation_payments
from . import duel_payments
from . import atomic_question_payments
from . import atomic_commerce_payments
from . import premium_payments
from . import ad_order_payments
from . import chat_reveal_payments
from . import payments
from . import chat

__all__ = ["router", "reset_inactivity_timer", "cancel_search_timer"]
