# A refused fix dispatch is posted on the PR, not swallowed (#2086)

## What changed

`scripts/run_failure_reactor.py` treated every non-zero `gh workflow run` as a crash: it raised a
plain `RuntimeError`, `make run-failure-reactor` exited 1, and the whole `react` job went red. The
only run that ever reaches that line is a **red PR** — a green reactor prints
`conclusion is 'success' - not a failure, nothing to do` — so the leg was unproven by any green run
and its first real exercise died on `HTTP 403 Resource not accessible by personal access token`
(run `42442836444`, job `react` `128615515251`, head `e51f2fd0`, 2026-11-08 03:28:16Z, workflow
`384587805` = `fix-bot.yml`).

Now the refusal is a fact the board can read:

- `DispatchRefused` carries the **HTTP status** and the **scope the credential lacks** — `workflow`
  for a classic PAT, `Actions: write` for a fine-grained one, "invalid or expired" for a 401,
  "not visible to the credential" for a 404, and `unknown` for anything the API did not name.
- `route()` catches it in Route A, calls `report_repair_unavailable()`, and returns **0**. The comment
  posted on the PR carries `repair unavailable: HTTP 403 — missing scope: …`, the raw `gh` detail,
  and the claim's own `bot-done` marker, so the PR is not left occupied for the whole claim TTL by a
  repair that never started. A `::warning::` annotation puts the same sentence in the Actions UI.
- An **unparseable** refusal is surfaced identically (`HTTP ?`), because "the API said something we
  do not understand" is still no repair.

The reactor's own reds therefore keep meaning *the reactor broke*; a dead repair leg now says
"no repair" on the branch that needed one. This is the second of the two fix directions #2086 named;
the credential itself is the owner's to scope (see Not covered).

## Why a red reactor job was the wrong signal

The 403 red `run-failure-reactor` on `main`'s tip reads, on every board that tracks reds, like a
main-tip failure — and the PR it was trying to repair said nothing at all. Two consumers were
therefore missing: the branch got no repair *and* no note that no repair was coming.

## Verified

- `~/llama-gguf-tools/.venv/bin/python -m pytest tests/test_run_failure_reactor.py -q` → 26 passed.
- Negative control (rule: prove the guard catches the bug): with `scripts/run_failure_reactor.py`
  stashed to `HEAD`, the three new cases fail — `assert 1 == 0` on the exit code, and
  `AttributeError: parse_dispatch_refusal` for the table test — and pass again once restored.

## Files

- `scripts/run_failure_reactor.py` — `DispatchRefused`, `missing_scope`, `parse_dispatch_refusal`,
  `report_repair_unavailable`, and the Route A `try/except`.
- `.github/workflows/run-failure-reactor.yml` — the `DISPATCH_TOKEN` comment now names the scope the
  token must carry and the refusal path.
- `docs/BOTS.md` — the reactor section documents the refusal route.
- `tests/test_run_failure_reactor.py` — three cases (posted + non-blocking, unparseable still
  surfaced, status→scope table).

## Not covered

- The dispatch **credential** itself: `secrets.BUMP_TOKEN` does not carry the dispatch scope, and
  minting/replacing a secret is the owner's action, not a code change. Filed as #2091, which also
  records that `docs/BOTS.md`'s credential table already says a dispatch should use
  `${{ github.token }}` and that `fix-bot`'s guard now admits `github-actions[bot]` on a
  `workflow_dispatch` (issue #1571) — so acceptance criterion 1 of #2086 ("a fix-bot run at the PR's
  head") needs that decision, not this PR.
- #2076 (the reactor's `agent:implement` labelling of pipeline failures) and #2072 (`**run:**`
  printing `displayTitle` instead of an id): different defects in the same script, untouched here.
