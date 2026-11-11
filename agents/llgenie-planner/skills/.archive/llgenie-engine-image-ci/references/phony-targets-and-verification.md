# Make target hygiene, the openspec tasks gate, and verification-run practice

Durable rules for llgenie repo work (llgenie's own `make` targets, gates, and CI).

## Every no-output target must be `.PHONY` — and the wiring guard now enforces it

`make` decides to run a recipe by looking for a FILE with the target's name. A
target that produces no file of its own name must be declared `.PHONY` —
otherwise a scratch file carrying that name shadows it and make prints
`make: '<target>' is up to date.` while running NOTHING and exiting 0: a green
no-op that reports success for a verification that never happened.

- Reproduce the failure before fixing it: `touch test-env && make test-env` →
  `make: 'test-env' is up to date.` with no recipe output and exit 0. Then add
  the target to the `.PHONY` block and the same tree runs the recipe. A test
  that asserts this needs the real `make`, not a Makefile parse.
- `scripts/check_wiring.py` (run by `ci-unit`) now fails on any parsed target
  that is neither declared `.PHONY` nor recorded. The `.PHONY` block in the
  Makefile uses continuation lines; parse the block, don't grep a single line.
- `make wiring-report` prints declared / recorded / undeclared counts and names
  any undeclared target.
- A target that genuinely writes a file of its own name is exempt only via a
  dated `not_phony` entry in `tests/fixtures/host-only-wiring.json`; a
  reasonless entry is refused and a stale one (target now phony or gone) is
  reported. When the rule first runs against the real tree it may find targets
  the issue missed — on first activation it caught an extra one in
  `tools/Makefile`. Trust the gate, add them.

## The openspec gate fails on unticked tasks — tick only after verification

`ci-openspec` runs `make openspec-tasks-check`, which FAILS a PR whose
`openspec/changes/<name>/tasks.md` still has any `- [ ]` box unticked (it names
the line numbers). So a freshly-pushed change whose verification is still
running is RED on `linux / openspec` by design. That is the gate working, not a
regression to chase: finish the verification, then tick every box and push —
the job goes green with the tick commit. Do not tick before the work is
verified (AGENTS.md: tick the moment the work is verified), and do not push
unticked work expecting a clean openspec run.

## Heavy `make test-unit` suites: run one at a time on the box

Two `make test-unit` runs (e.g. local + a second worktree's) contending on one
host end in SIGKILL (`Error 137`), not a test failure. Run the heavy hermetic
suite alone, boxed to itself, and read the log rather than the process widget
(which shows 0 s while a piped `tail` run is still producing — the run is alive).

## Rotating a CI secret right

- Set the GitHub Actions secret with the value piped via stdin, never in an
  argument list, and verify it by reading back `updated_at` / visibility
  (`gh secret list`). Never print the value.
- After setting, fire the workflow that consumes the key once (hand dispatch
  on `main`) and confirm from the run's own log that the new value worked — a
  secret set but never exercised is unverified.

## Sync latest upstream main before ANY new issue work

The user's standing, unconditional rule: before creating/resuming an issue's
branch or implementing, `git fetch --all --prune` + pull/merge latest `main`
from the upstream owner and cut the worktree from that exact tip. A branch
ahead of that tip is rejected at the merge gate. Do this every time, and state
that it ran before claiming a PR is ready.
