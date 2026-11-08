# ci-verdict reads every check-run on a busy head — a 100-row page is not a refusal (issue #2156) — 2026-11-08

**Implements:** issue #2156 — the run-failure reactor's sole surviving tracker (the six
duplicates #2115 #2120 #2133 #2150 #2153 #2154 were collapsed into it). `ci-verdict` judged a
finished CI run from the head's check-runs (`scripts/ci_verdict.py::check_runs_of`, added for #2116),
but it read **one page of 100** and refused anything larger as "truncated". A busy `main` head exceeds
that. Measured 2026-11-08 on CI run **42452592982** (`push`, head `520db900`, branch `main`): the
head reported **192** check-runs and one page returned 100, so the verdict exited 2 with
`head 520db900... reports 192 check-run(s) and one page returned 100: a truncated listing cannot be a
verdict` — and because no `--check-run-out` payload had been written, the workflow's `Post the verdict`
step died on `no check-run payload: the verdict step did not reach a verdict`. The head carried **no**
`ci-verdict` row, and the run-failure reactor filed a new issue for every rejudge of the same class
(hence the seven trackers).

## What changed

- **`scripts/ci_verdict.py`** — `check_runs_of` now walks pages, exactly like `branch_runs` (#1617):
  page 1 carries no `&page=` (GitHub treats a bare listing as page 1, and that is the shape the
  pre-#2116 stubs and the workflow's older reads matched), every later page appends `&page=N`, rows
  are deduped by id, and the #1582/#1610 truncation guard now binds only on a **genuine shortfall** —
  when the pages that can be read still fall short of `total_count`, or a page ends early and the next
  adds nothing. An **empty** listing (`total_count == 0`, the shape every #2116 fixture answers) is a
  clean `[]`, never a false refusal. The error path is unchanged: a verdict that cannot be reached
  still exits 2 with **no** check-run (the settle-gate and unreadable-artifact tests assert that
  deliberate choice — an unreachable verdict must never post a possibly-wrong verdict; the reactor
  still files the issue).
- **`tests/test_ci_verdict.py`** — three new hermetic tests: `test_a_multi_page_check_run_listing_is_
  fully_walked` (192 rows across two pages, all collected — the #2156 specimen shape),
  `test_a_genuinely_short_check_run_listing_still_raises` (pages fall short, the guard still binds),
  and `test_an_empty_check_run_listing_is_not_truncation` (`total_count == 0` returns `[]`).

## Proof

- **Prove-guard:** on the pre-fix `check_runs_of` (one page, refuse over 100),
  `test_a_multi_page_check_run_listing_is_fully_walked` **FAILS with the exact #2156 error** (`head
  5555... reports 192 check-run(s) and one page returned 100`); on the fixed script it passes.
- **Live reproduction of the issue's own specimen:** `make ci-verdict REPO=asimov-agent/llgenie
  RUN_ID=42452592982 HEAD_SHA=520db900598ef800bf44c1fe9883c778f523019b CHECK_RUN_OUT=/tmp/v.json` at
  the branch head now reads all **192** check-runs, reports `verdict=green success=10 failure=0`, names
  the 14 unjudged blocking rows (the dozen `judge` failures the reactor filed + two `auto-merge`
  cancellations — the #2116 names-the-red contract), and writes the payload `conclusion=neutral`
  (SUPERSEDED by a later `main` run) — rc 0. Pre-fix the same command exited 2 on the truncation.
- **Full `tests/test_ci_verdict.py`: 49 passed** (46 prior + 3 new) under `$HOME/llama-gguf-tools/.venv`.

## Why it matters

The verdict is the only surface every lane, bot and human reads before touching a PR or a head. A head
that cannot be read cleanly has to become a `ci-verdict` row that reaches a real decision (or honestly
names the unjudged reds) — not a silent `exit 2` that leaves no row and spawns a duplicate issue per
rejudge.

## Not covered

- The duplicate-**filing** problem itself (7 issues from one class of failure) — the reactor's dedupe
  is issue #1990's half; the planner's orchestrator comment on #2156 names the duplicator behaviour as
  a separate concern.
- #2116 (judging only the `CI` workflow) — already landed separately; this change keeps its
  names-the-red contract intact.

## Acceptance criteria

- [x] a busy head with > 100 check-runs is read completely (all rows collected, verdict reached)
- [x] a listing that still falls short of `total_count` is refused ("truncated listing", never a verdict)
- [x] an empty head returns `[]` (not a false refusal), keeping every #2116 fixture green
- [x] the real #2156 specimen (`run 42452592982`, head `520db900`) reaches a verdict at the branch head
- [x] the four gates are green at the head: `make check-docs`, `make check-workflows`,
      `make check-wiring`, `make lint`
