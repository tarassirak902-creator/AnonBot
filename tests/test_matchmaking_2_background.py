from pathlib import Path


def test_background_worker_runs_matchmaking_recovery() -> None:
    source = Path("app/services/background.py").read_text(encoding="utf-8")
    assert "async def matchmaking_recovery_loop()" in source
    assert "recover_matchmaking_state()" in source
    assert 'name="matchmaking_recovery"' in source
    assert "matchmaking_auto_recovery" in source


def test_startup_still_repairs_matchmaking_state() -> None:
    source = Path("app/main.py").read_text(encoding="utf-8")
    assert "await db.repair_matchmaking_state()" in source
