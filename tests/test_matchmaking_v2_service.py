from pathlib import Path


def test_matchmaking_v2_uses_canonical_atomic_repository() -> None:
    source = Path("app/services/matchmaking_service.py").read_text(encoding="utf-8")
    assert "from app.database.matchmaking_repository import try_match_user" in source
    assert "BEGIN IMMEDIATE" in source
    assert "recover_matchmaking_state" in source
    assert "matchmaking_health" in source


def test_matchmaking_recovery_repairs_transient_state_only() -> None:
    source = Path("app/services/matchmaking_service.py").read_text(encoding="utf-8")
    assert "DELETE FROM active_chats" in source
    assert "DELETE FROM queues" in source
    assert "DELETE FROM users" not in source
    assert "DELETE FROM purchases" not in source
    assert "DELETE FROM recent_partners" not in source


def test_matchmaking_adapter_is_installed_before_handlers() -> None:
    init = Path("app/handlers/__init__.py").read_text(encoding="utf-8")
    adapter = Path("app/handlers/matchmaking_v2_adapter.py").read_text(encoding="utf-8")
    assert "install_matchmaking_v2()" in init
    assert init.index("install_matchmaking_v2()") < init.index("from . import questions")
    assert "shared.db.try_match_user = _try_match_user" in adapter
    assert "shared.db.remove_from_queue = _remove_from_queue" in adapter


def test_recovery_requires_reciprocal_active_chat_rows() -> None:
    source = Path("app/services/matchmaking_service.py").read_text(encoding="utf-8")
    assert "peer.user_id=active_chats.partner_id" in source
    assert "peer.partner_id=active_chats.user_id" in source
    assert "user_id=partner_id" in source
