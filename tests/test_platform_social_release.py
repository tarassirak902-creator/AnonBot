from pathlib import Path

from app.database.platform_social_repository import ReputationSummary
from app.handlers.commercial_navigation_ui import _more_keyboard
from app.handlers.platform_social_ui import _community_keyboard


INIT = Path("app/handlers/__init__.py").read_text(encoding="utf-8")
DB_INIT = Path("app/database/__init__.py").read_text(encoding="utf-8")
REPOSITORY = Path("app/database/platform_social_repository.py").read_text(encoding="utf-8")
UI = Path("app/handlers/platform_social_ui.py").read_text(encoding="utf-8")


def _callbacks(keyboard) -> set[str]:
    return {
        button.callback_data
        for row in keyboard.inline_keyboard
        for button in row
        if button.callback_data
    }


def test_reputation_summary_is_safe_without_votes() -> None:
    summary = ReputationSummary(0, 0, 0)
    assert summary.total == 0
    assert summary.positive_percent == 0


def test_reputation_summary_rounds_positive_share() -> None:
    summary = ReputationSummary(9, 1, 0)
    assert summary.total == 10
    assert summary.positive_percent == 90


def test_community_is_visible_from_more_hub() -> None:
    assert "platform_community" in _callbacks(_more_keyboard())


def test_community_routes_cover_reputation_notifications_and_navigation() -> None:
    callbacks = _callbacks(_community_keyboard(3))
    assert callbacks == {
        "platform_reputation",
        "platform_notifications",
        "profile_social_contacts",
        "nav_profile_home",
    }


def test_social_repository_prevents_duplicate_dialog_vote() -> None:
    assert "UNIQUE(rater_id, dialog_key)" in REPOSITORY
    assert "rating IN (-1, 0, 1)" in REPOSITORY
    assert "rater_id == rated_user_id" in REPOSITORY


def test_notifications_are_private_and_scoped_to_owner() -> None:
    assert "WHERE user_id = ?" in REPOSITORY
    assert "user_id INTEGER NOT NULL" in REPOSITORY
    assert "callback.from_user.id" in UI


def test_platform_social_modules_are_registered() -> None:
    assert "from .platform_social_repository import *" in DB_INIT
    assert "from . import platform_social_ui" in INIT
    assert INIT.index("from . import platform_social_ui") < INIT.index("from . import chat")
