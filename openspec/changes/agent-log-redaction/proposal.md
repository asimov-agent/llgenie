# agent-log-redaction — proposal

Issue: [#359](https://github.com/asimov-agent/llgenie/issues/359) (child of [#357](https://github.com/asimov-agent/llgenie/issues/357))

## Why

A bot's agent stream **is** the job's console output: `make implement-issue` writes whatever the agent
printed straight into the step log, and nothing bounded it. GitHub masks the secret values it
*registers*, and that is a filter over the stream, not a property of the content — a value that is
transformed (URL-encoded, base64, a slice) sails past it, and nothing is masked at all in a log a job
uploads itself. So a bot run is simultaneously **un-reviewable** (no transcript is kept) and
**undefended** (the moment anyone publishes one, it is raw).

Measured on `main@6338fc6`:

```
$ grep -rn 'upload-artifact' .github/workflows/      # no hits anywhere
$ ls scripts/scrub_log.py                            # No such file or directory
$ grep -n 'HERMES_LOG\|scrubbed' Makefile            # no hits
```

The sibling repo answered it with one seam: `HERMES_LOG` / `HERMES_LOG_SCRUBBED`, `scripts/scrub_log.py`
(read values **by name**, mask every spelling and shape), **one** `scrubbed_run` macro every leg goes
through, and the REDACTED copy uploaded as the artifact (`trending-local-llms` `fix-bot.yml:205`,
`issue-bot.yml:491,508`).

## What Changes

- **`scripts/scrub_log.py`**: reads the secret VALUES by NAME from its environment — the list lives
  once, in `scripts/check_secret_output.py::SECRET_VARS` — and replaces every raw / URL-encoded /
  base64 spelling with `***`, plus credential SHAPES (`ghp_…`, `github_pat_…`, `hf_…`, `sk-…`,
  `ev_…`, `Bearer …`) that never entered its environment. It prints the redacted lines and a COUNT:
  never a value, never a prefix, never a length. A missing input is exit 2.
- **Makefile**: `HERMES_LOG` / `HERMES_LOG_SCRUBBED` / `HERMES_LOG_TAIL` (gitignored) and ONE macro,
  `$(call scrubbed_run,<command>)` — the stream is captured, only the redactor's bounded tail prints,
  and the command's own exit status survives (the command runs in a subshell, so a leg that calls
  `exit` still gets redacted). **Every public agent leg** goes through it: `issue-refiner`,
  `issue-bot-triage`, `implement-issue`, `hermes-smoke`, `rebase-bot-agent`, `agent-jev-preflight`,
  `fix-loop-image` (whose `LOG=` now receives the REDACTED copy). A public `scrub-log` target exposes
  the redactor for a human.
- **Workflows**: `fix-bot.yml`, `issue-bot.yml`, `issue-refiner.yml`, `rebase-bot.yml` upload the
  REDACTED transcript as the `agent-transcript-redacted` artifact — never the raw file.
- **`tests/test_scrub_log.py`** (in `make test-unit`): the spellings and shapes are masked and prose
  survives; a short value is left alone; a missing input exits 2; only a bounded tail prints; the REAL
  macro (through the real Makefile) keeps a sentinel out of the console, writes the redacted artifact
  and keeps the command's exit status; every public agent leg uses the macro; every bot job publishes
  the redacted file.
- **`AGENTS.md`** + **`README.md`**: the durable rule and the navigation entry.
- **`agent-wiki/2026-10-19-agent-log-redaction.md`**: the work record.

## Impact

- A bot run becomes reviewable (a redacted transcript is kept as an artifact) without publishing a
  single key value.
- One seam, not seven: a new leg cannot forget the redaction, and the suite fails on a leg that prints
  raw or a workflow that uploads the raw file.
- Out of scope, filed separately: a committed-credential scanner that reads a VALUE
  ([#360](https://github.com/asimov-agent/llgenie/issues/360)) and the two `check_secret_output` rule
  families that make an unredacted upload catchable
  ([#361](https://github.com/asimov-agent/llgenie/issues/361)).
