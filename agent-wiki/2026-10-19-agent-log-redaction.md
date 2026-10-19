# 2026-10-19 — the agent's transcript is redacted before it prints (issue #359)

Implements [#359](https://github.com/asimov-agent/llgenie/issues/359) (PR [#366](https://github.com/asimov-agent/llgenie/pull/366)),
the second child of the
bot-fleet parent [#357](https://github.com/asimov-agent/llgenie/issues/357). OpenSpec change:
`openspec/changes/agent-log-redaction`.

## What was wrong (measured)

A bot's agent stream is the job's console output, and nothing bounded or masked it: no
`upload-artifact` anywhere in the repo, no `scripts/scrub_log.py`, no `HERMES_LOG`, and the fix loop's
`tee` wrote the raw stream wherever the caller pointed it. GitHub masks registered values in its own
log stream only — a transformed value (URL-encoded, base64, a slice) sails past, and nothing is masked
in a log a job uploads itself. So a finished run was neither reviewable nor defensible.

## What changed

- **`scripts/scrub_log.py`** (new): reads the secret values BY NAME from its environment (the ONE list
  in `check_secret_output.py::SECRET_VARS`), masks every raw / URL-encoded / base64 spelling plus
  credential shapes (`ghp_`, `github_pat_`, `hf_`, `sk-`, `ev_`, `Bearer …`), prints a bounded tail
  and a COUNT — never a value, a prefix or a slice. A missing input is exit 2.
- **Makefile**: `HERMES_LOG` / `HERMES_LOG_SCRUBBED` / `HERMES_LOG_TAIL` + ONE
  `$(call scrubbed_run,…)` macro (the command runs in a subshell, so a leg that calls `exit` cannot
  skip the redaction, and its exit status survives), applied to all seven public agent legs;
  `fix-loop-image`'s `LOG=` now receives the REDACTED copy; a public `scrub-log` target exposes the
  redactor.
- **Workflows**: the four bot jobs upload `hermes-run.scrubbed.log` as `agent-transcript-redacted`.
- **`.gitignore`**, **AGENTS.md** (the durable rule), **README.md**, **`agent-wiki/`**, and
  `tests/test_scrub_log.py` (9 tests) wired into `make test-unit`.

## Verified

- `pytest tests/test_scrub_log.py -q` → 9 passed, including the REAL macro through the real Makefile:
  a fixture leg printing a sentinel and exiting 3 leaves no sentinel on the console, writes `***` into
  the REDACTED file, and make still reports `Error 3`.
- `make check-wiring`, `make check-docs`, `make check-secret-output`, `make check-workflows`,
  `make lint`, `make openspec-validate NAME=agent-log-redaction`.

## Decisions

- **The seam lives in the public legs**, not in each internal recipe: those run inside the container,
  and the public leg is the single place their stdout passes through — the same choice the sibling
  repo made (its `scrubbed_run`), for the same reason (a leg that repeats redaction by hand is how the
  fix loop gets missed).
- **The subshell is deliberate**: `{ …; }` would let a command's own `exit` skip the redaction and
  leave the raw stream on the console — found while writing the test that proves the exit status
  survives.
- **No second value list**: the redactor imports `SECRET_VARS` from `check_secret_output.py`, so a key
  added to the guard is redacted by the seam without a second edit.

## Follow-ups

- Next: the two `check_secret_output` rule families that make an unredacted upload catchable (#361),
  the committed-credential scanner (#360), the masked web reach (#362, depends on #358's seam), and
  the loud missing-key guard for every leg (#363). #358 (the `_HERMES_FORCE_` seam) is already
  implemented in PR #365; this change is written against `main` and will be rebased onto it when it
  merges (the two additions meet in the same Makefile region: one adds the credential list, this one
  adds the log seam).
