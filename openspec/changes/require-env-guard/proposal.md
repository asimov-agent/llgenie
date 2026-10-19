# require-env-guard — proposal

Issue: [#363](https://github.com/asimov-agent/llgenie/issues/363) (child of [#357](https://github.com/asimov-agent/llgenie/issues/357))

## Why

Exactly **one** bot leg refused to start when its provider key was unset — `make hermes-smoke`, with an
ad-hoc bash test. The other six forwarded `-e NOUS_API_KEY` / `-e TYPESAFE_API_KEY` and only failed
**inside** the container, after `scripts/ci_images.py ensure agent` had pulled the image and started
one, on a job with a 120-180 minute timeout. The log then reads like a model problem, not a plumbing
mistake, which is the expensive part.

Measured on `main@2649803`:

```
$ grep -n 'test -n "$$NOUS_API_KEY"' Makefile        # one hit (hermes-smoke)
$ grep -c 'require_env' Makefile                     # 0
```

The sibling repo has one named guard for this (`scripts/require_env.py`), independent of its smoke.

## What Changes

- **`scripts/require_env.py`**: name-only messages, exit 2 on the first missing or EMPTY variable, a
  bad name refused, and never a value, prefix or length printed.
- **`make require-env KEYS="…"`** — the public target a human runs, and the same code path the legs use.
- **Every leg that starts the agent image** runs the guard as its FIRST recipe line, ahead of
  `scripts/ci_images.py ensure agent`: `rebase-bot-agent`, `issue-refiner`, `issue-bot-triage`,
  `agent-jev-preflight`, `implement-issue`, `hermes-smoke`, `fix-loop-image`, `agent-shell-keys-check`.
- **One code path**: the ad-hoc bash test in `hermes-smoke` and `_hermes-smoke` is replaced by the
  script, so there is nothing left to drift.
- **`tests/test_require_env.py`** (in `make test-unit`): the guard's behaviour (missing, empty, present,
  name validation), and the wiring — the roster is derived from the Makefile, and every agent leg must
  run the guard BEFORE the image pull.
- **README.md**, **AGENTS.md**, **`agent-wiki/`**.

## Impact

- A missing secret costs seconds instead of a 120-180 minute run, on every leg, not just one.
- The roster cannot rot: a new leg without the guard fails the suite (the pattern this repo already
  filed twice — #349, #301).
- Out of scope, filed separately: #364 (the issue-bot implementer's job sets no `GH_TOKEN`, so that leg
  forwards an empty one) and the secret definitions themselves, which are repository settings.
