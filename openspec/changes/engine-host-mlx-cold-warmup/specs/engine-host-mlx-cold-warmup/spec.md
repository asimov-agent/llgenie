# engine-host-mlx-cold-warmup

## ADDED Requirements

### Requirement: the cold-model first /v1/chat/completions gets the full configured warm-up window

The host-verify assertion MUST give the first `/v1/chat/completions` after READY the full
configured timeout as its budget (not a fixed 120s pre-cap), because some engines (mlx-cpu) load
the model lazily on the first prompt — a health-READY / first-token-timeout split is a cold-start
artifact, not a serving bug (issue #1894, run `42318302931` job `128236450093`).

WHEN `serve_published` asserts llm-local after READY
THEN `_chat` receives the full configured window and attempt 0 uses it.

#### Scenario: a lazy-load engine answers within its window

- **Given** `serve_published` with a 900s configured timeout
- **When** the first `/v1/chat/completions` triggers a lazy model load
- **Then** attempt 0 gets the full 900s window (not the old `min(timeout,120)` cap) and the engine
  answers
- **Test:** `test_serve_published_passes_the_full_warmup_window_to_chat` asserts 900 reaches `_chat`; `test_chat_first_attempt_gets_the_cold_model_warmup_budget` asserts attempt 0 budget 900 and retry 120

### Requirement: a genuine hang stays time-bounded and fails loudly

The retry budget after the cold first attempt MUST cap at the conversation-norm
`_CHAT_RETRY_CAP_S=120` seconds, so a lazy-load miss is retried on the now-warm vertex while a true
serving hang is still bounded and still fails loudly (never weakened).

WHEN `_chat` retries after a first-attempt timeout
THEN the retry budget is `min(timeout, _CHAT_RETRY_CAP_S)` and the exception still propagates after
`retries`.

#### Scenario: a hang fails loudly after bounded retries

- **Given** a `/v1/chat/completions` that never answers
- **When** `_chat` runs with `retries` attempts
- **Then** each retry budget is capped at 120s and the last exception is re-raised
- **Test:** `test_chat_budget_narrows_on_caller_timeout_below_the_cap` asserts the caller's
  sub-cap timeout is the exact budget on both attempts
