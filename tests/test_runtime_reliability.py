from pathlib import Path

import pytest

from app.core.middlewares import UpdateObservabilityMiddleware


MAIN = Path("app/main.py").read_text(encoding="utf-8")
MIDDLEWARES = Path("app/core/middlewares.py").read_text(encoding="utf-8")


def test_observability_middleware_validates_ttls() -> None:
    with pytest.raises(ValueError):
        UpdateObservabilityMiddleware(callback_ttl=0)
    with pytest.raises(ValueError):
        UpdateObservabilityMiddleware(callback_ttl=3, cache_ttl=3)


def test_observability_is_registered_for_messages_and_callbacks() -> None:
    assert "observability = UpdateObservabilityMiddleware" in MAIN
    assert "dispatcher.message.outer_middleware(observability)" in MAIN
    assert "dispatcher.callback_query.outer_middleware(observability)" in MAIN


def test_matchmaking_repair_runs_before_polling() -> None:
    assert MAIN.index("await db.repair_matchmaking_state()") < MAIN.index("await dispatcher.start_polling(bot)")


def test_middleware_contains_duplicate_and_error_guards() -> None:
    assert "duplicate_update" in MIDDLEWARES
    assert "route_start" in MIDDLEWARES
    assert "route_done" in MIDDLEWARES
    assert "route_error" in MIDDLEWARES
    assert "Не удалось выполнить действие" in MIDDLEWARES


def test_callback_cache_is_bounded_by_periodic_pruning() -> None:
    assert "self._processed % 500 == 0" in MIDDLEWARES
    assert "self._prune(time.monotonic())" in MIDDLEWARES
