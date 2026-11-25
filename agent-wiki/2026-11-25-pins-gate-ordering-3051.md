# 2026-11-25 — the pins gate awaits the image producer its own lane started (issue #3051)

## What was verified against the issue

- The race is reproduced in the issue's own numbers (PR #3030 head `20b3f0307`, job `137931122978`,
  run `45242589912`): `[pins] NOT PUBLISHED … vllm:0c57b419-…-cpu (HTTP Error 404)` at 19:08:53Z,
  `[ci_unit] FAILED step 15/54`, while the producer job `engine-build-pr-trigger` ran 18:50:31Z →
  20:50:34Z in the same lane. `needs:` cannot express the order because the producer is a separate
  workflow, so the pins step read a GHCR snapshot from before the run started.
- Ordering seam (issue #3051 AC3): `pipeline.yml`'s `unit` job — the job `ci.yml`'s `linux` lane calls
  at `ci.yml:509`; `ci.yml` has no `make ci-unit` step of its own — now runs
  `make engine-pins-await` immediately before `make ci-unit`, with
  `ENGINE_PINS_AWAIT_SECONDS: "2700"` (measured producer cell build: 2771 s, `test-build-engine-image`
  on PR #3030) and `actions: read` on the job token (the #893 lesson: a missing grant is a 403).
- `scripts/engine_pins_await.py` is read-only and bounded: it lists this repository's
  `engine-build-pr-trigger.yml` runs through `gh api` and prints `AWAIT <run_id> <status>`; it never
  dispatches, re-triggers, re-runs or cancels, and every outcome exits 0 — the verdict belongs to the
  pins gate. `ENGINE_PINS_AWAIT_SECONDS` defaults to 0 (one lookup, no wait).
- Split verdicts (AC1/AC2) in `scripts/check_engine_pins_published.py`: for cells THIS change repins,
  a PR lane prints `PINS-PENDING <ref>` / `ALIAS-PENDING <ref>` plus `PINS DEFERRED <n>` and exits 0;
  `main`/`push` semantics keep `NOT PUBLISHED` + `[select]` + exit 1, a gap in a pin the change did
  not move stays hard red, and `check_committed` (the `--all` sweep) never defers whatever the event.
  Mode comes from `ENGINE_PINS_PR_PENDING`, with a `GITHUB_EVENT_NAME == pull_request` fallback.
- Tests: `tests/test_engine_pins_await.py` (16 cases, hermetic — injected `run_lookup`, no network,
  including an AST read that the seam issues no `dispatches`/`reruns`/`cancel`/`POST`, a read that
  its `gh api` call goes through `scripts/proc.py`, and a read of
  `pipeline.yml`'s `unit` job step list that fails if the await moves after `make ci-unit`) and 4 new
  cases in `tests/test_check_engine_pins_published.py` (PR defers an unpublished repin / main control
  hard-reds the same ref / committed sweep never defers / event-derived mode when the knob is unset).
- Live seam read at the head: `GITHUB_REPOSITORY=asimov-agent/llgenie BASE=f7eb17d02
  ENGINE_PINS_AWAIT_SECONDS=60 make engine-pins-await` rc=0 — it named the 12 repinned engines and
  made the real runs API lookup ("no engine-build-pr-trigger.yml run for this head; nothing to
  await"). `make check-engine-pins-published` on the same base rc=0 in both modes with all 26
  repinned cells `PUBLISHED`, i.e. a settled wave no longer produces a false red.
- Gates measured at the head: lint, `check-wiring`, `check-workflows` (actionlint),
  `openspec-validate NAME=pins-gate-ordering` rc=0, the named test modules (107 passed), and the
   full `make test-unit` battery (4460 passed, 0 skipped) at head 1f32eaee5.

## Decisions

- The seam is a **step order**, not a `needs:` edge: GitHub cannot order a job across workflows, so the
  lane waits for what it started instead of pretending the read is safe. The await never reddens:
  a bounded window that expires is not a failure, it is the state the pins gate must describe.
- Deferral is scoped to *this change's* repinned cells only. Loosening it to "any pin may be missing
  in a PR lane" would have deleted the #178 discipline the committed sweep exists to enforce.
- `GITHUB_REPOSITORY` is the seam's only repo source (CI sets it); with it unset the seam prints a
  WARN and exits 0 rather than guessing a repo, and the pins gate decides on its own.
- A producer run is matched by its workflow **file** (`path` in the Actions runs API), never by `name`:
  the API reports the workflow's display title truncated at 64 chars, so the first version filtered on
  `name` and printed "no engine-build-pr-trigger.yml run for this head" while run 45242589764 for PR
  #3030's head sat completed for that exact head. The hermetic fixture now carries the real row shape
  (`name` = display title, `path` = `.github/workflows/…`) so a fixture cannot hide the API again.
- Out of scope, filed as its own issue: observing the next real bump wave green at its heads
  (#3061); the ~2 h `trigger` cost stays #2891; the bump lanes' missing PR-body/OpenSpec half stays
  #3050.

## The first CI red: the seam had to join the subprocess policy module

The pushed lane reddened `make ci-unit` at step 28/54, `make check-proc-gate`, on
`scripts/engine_pins_await.py:59: proc = subprocess.run(["gh", "api", path], …)`. Issue #797 confines
`subprocess.run/check_output/Popen` in `scripts/` to `scripts/proc.py` or a `# proc-allow:` line, and
the tracked exemption list is a remainder, not a place for new code — so `_gh_api` now calls
`proc.run_ok` (the policy's never-raises-on-non-zero shape, which is exactly what a seam that must
never redden a lane needs; it reports the command's stderr itself) with `GH_API_TIMEOUT_SECONDS =
60.0` so a hung `gh api` read becomes a `WARN` the pins gate decides past instead of a wedge. The new
cross-group import (`CI entrypoints` -> `Structural gates`) is stated in `scripts/package-layers.json`
with the issue #797 reason, and `test_the_seam_reads_gh_through_the_subprocess_policy_module` pins the
rule so a later edit cannot put the direct call back. Measured: `make check-proc-gate` rc=0,
`make check-package-layers` rc=0 (190 modules, 82 stated edges, 0 cycles), the two named modules
69 passed, the four-module line 108 passed.

## Current status

Branch `feat/pins-gate-ordering` (off `origin/main`), OpenSpec change `pins-gate-ordering`, issue
#3051. Battery at head 1f32eaee5da91dad440551f6edd88c7387a255f5: `make test-unit` rc=0, 4460 passed /
13638 deselected / 0 skipped. Issue body, OpenSpec change and code carry the same goal; the live-wave half is #3061.
