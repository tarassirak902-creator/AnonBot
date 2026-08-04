# Question module architecture

The anonymous-question feature is being migrated from a single handler module to explicit application services.

## Current boundaries

- `question_start_context.py` owns bounded, expiring context created by personal links.
- `question_receiver.py` owns authorization and receiver resolution for question commerce flows.
- `question_presentation.py` owns display names, timestamps and list item models.
- `question_navigation.py` owns page size and offset rules.
- `question_handler_bridge.py` adapts these services to the existing aiogram handler API.

## Compatibility bridge

The bridge is intentionally temporary. It lets production handlers keep their callback data, FSM states and payment payloads while state and domain rules move into isolated, tested modules. New business rules should be added to services rather than to `questions.py`.

## Next extraction

A later PR should physically split `questions.py` into entry, inbox, answers and commerce routers. At that point the bridge can be deleted and each router can use explicit imports instead of `from .shared import *`.

## Invariants

- User-visible text, callback data and invoice payloads remain backward compatible.
- Temporary context is bounded and expires automatically.
- Receiver resolution always verifies ownership and rejects self-targeting.
- Pagination offsets are normalized and page-size rules are centralized.
