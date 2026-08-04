from app.services import QuestionStartContext, QuestionStartContextStore


class FakeClock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


def context(owner_id: int) -> QuestionStartContext:
    return QuestionStartContext(
        token=f"token-{owner_id}",
        owner_id=owner_id,
        display_name=f"User {owner_id}",
    )


def test_context_expires_after_ttl() -> None:
    clock = FakeClock()
    store = QuestionStartContextStore(ttl_seconds=60, clock=clock)
    store.put(10, context(20))

    clock.advance(61)

    assert store.get(10) is None
    assert len(store) == 0


def test_read_reordering_does_not_keep_expired_context_alive() -> None:
    clock = FakeClock()
    store = QuestionStartContextStore(ttl_seconds=10, clock=clock)
    store.put(1, context(11))
    clock.advance(5)
    store.put(2, context(22))

    # Reading user 1 moves it to the LRU tail, but must not renew its TTL.
    assert store.get(1) == context(11)
    clock.advance(6)

    assert store.get(1) is None
    assert store.get(2) == context(22)
    assert store.keys_snapshot() == (2,)


def test_store_evicts_oldest_entry_at_capacity() -> None:
    clock = FakeClock()
    store = QuestionStartContextStore(max_entries=2, clock=clock)
    store.put(1, context(11))
    clock.advance(1)
    store.put(2, context(22))
    clock.advance(1)
    store.put(3, context(33))

    assert store.get(1) is None
    assert store.get(2) == context(22)
    assert store.get(3) == context(33)


def test_put_replaces_existing_user_context() -> None:
    store = QuestionStartContextStore()
    store.put(1, context(10))
    store.put(1, context(20))

    assert len(store) == 1
    assert store.get(1) == context(20)


def test_pop_consumes_context_once() -> None:
    store = QuestionStartContextStore()
    expected = context(20)
    store.put(1, expected)

    assert store.pop(1) == expected
    assert store.pop(1) is None
