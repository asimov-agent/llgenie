# The repo's workflows must not read a secret the repo does not define (issue #311)

**Issue:** [#311](https://github.com/asimov-agent/llgenie/issues/311)
**Capability:** `bot-secret-wiring`

## Why

Exercising `issue-refiner.yml` surfaced a secret-wiring gap. Its `refine` job set two environment
variables from secrets the repo does not define:

```
$ grep -n 'OPENROUTER_API_KEY\|OPENCODE_API_KEY' .github/workflows/*.yml
.github/workflows/issue-refiner.yml:71:      OPENROUTER_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}
.github/workflows/issue-refiner.yml:72:      OPENCODE_API_KEY: ${{ secrets.OPENCODE_API_KEY }}

$ gh secret list --repo asimov-agent/llgenie
BUMP_TOKEN  HF_TOKEN  NOUS_PORTAL_API_TOKEN  TYPESAFE_API_KEY
```

GitHub substitutes an EMPTY string for a secret that does not exist, so the agent container received
`OPENROUTER_API_KEY=""` and `OPENCODE_API_KEY=""`. The bot's JEV preflight picks the provider key by
provider (`scripts/agent_jev_preflight.sh`: `openrouter` -> `OPENROUTER_API_KEY`, `opencode` ->
`OPENCODE_API_KEY`), and `scripts/install_nerve_ci.sh` iterated all three - but only
`TYPESAFE_API_KEY` is defined. If the provider ever moved to `openrouter`/`opencode`, the bot would
run with an empty key and fail (or degrade) with no wiring error at the point of the switch. The
other bots (`issue-bot.yml`, `fix-bot.yml`, `rebase-bot.yml`) passed only `NOUS_API_KEY` +
`TYPESAFE_API_KEY`, so the refiner was the odd one out.

The keys are never used: `HERMES_NERVE_PROVIDER` is `typesafe` (the repo's only provider), so the
`openrouter`/`opencode` branches are dead code that names secrets the repo does not define.

## What Changes

- **`.github/workflows/issue-refiner.yml`** - drops the two `secrets.OPENROUTER_API_KEY` /
  `secrets.OPENCODE_API_KEY` env lines; the job passes only the keys it needs.
- **`scripts/agent_jev_preflight.sh`** - the provider case accepts `typesafe` only; `openrouter` /
  `opencode` are no longer named as providers (they were never configured).
- **`scripts/install_nerve_ci.sh`** - the key loop checks `TYPESAFE_API_KEY` alone.
- **`Makefile`** - the four agent recipes stop passing `-e OPENROUTER_API_KEY -e OPENCODE_API_KEY`
  through to the container.
- **`scripts/check_secret_output.py`** - `SECRET_VARS` drops the two names; the docstring defines the
  list as "the variables that carry a credential in this repo", and they no longer do. The
  `check-secret-output` guard still scans every other key.
- **`README.md`** - the "No secret value reaches a log" list drops the two names.

## Impact

No workflow reads a `secrets.X` the repo does not define. The JEV preflight names the provider it
actually uses (`typesafe`), so a future provider switch fails loudly at the preflight instead of
silently running with an empty key.

## Not covered

- The build-time leak guard in `containers/agent/Dockerfile` still greps for the
  `TYPESAFE|OPENROUTER|OPENCODE` provider-key namespace: it is a defence against baking ANY provider
  key into the image, not a wiring reference, and the `agent-nerve-jev` spec names all three. Kept
  intact on purpose.
