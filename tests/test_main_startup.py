import pytest

import app.main as main_module


class Observer:
    def outer_middleware(self, middleware) -> None:
        pass


class FakeDispatcher:
    def __init__(self) -> None:
        self.message = Observer()
        self.callback_query = Observer()

    def include_router(self, router) -> None:
        pass

    async def start_polling(self, bot) -> None:
        pass


class FakeSession:
    async def close(self) -> None:
        pass


class FakeBot:
    last_instance = None

    def __init__(self, token: str) -> None:
        self.token = token
        self.session = FakeSession()
        self.drop_pending_updates = None
        FakeBot.last_instance = self

    async def set_my_commands(self, commands) -> None:
        pass

    async def set_chat_menu_button(self, menu_button) -> None:
        pass

    async def delete_webhook(self, *, drop_pending_updates=None) -> bool:
        self.drop_pending_updates = drop_pending_updates
        return True


@pytest.mark.asyncio
async def test_startup_preserves_pending_updates(monkeypatch) -> None:
    async def no_op(*args, **kwargs):
        return None

    monkeypatch.setattr(main_module, "Bot", FakeBot)
    monkeypatch.setattr(main_module, "Dispatcher", FakeDispatcher)
    monkeypatch.setattr(main_module, "setup_logging", lambda: None)
    monkeypatch.setattr(main_module.db, "init_db", no_op)
    monkeypatch.setattr(main_module.db, "repair_matchmaking_state", no_op)
    monkeypatch.setattr(main_module, "create_background_tasks", lambda bot: [])
    monkeypatch.setattr(main_module, "stop_background_tasks", no_op)

    await main_module.main()

    assert FakeBot.last_instance is not None
    assert FakeBot.last_instance.drop_pending_updates is False
