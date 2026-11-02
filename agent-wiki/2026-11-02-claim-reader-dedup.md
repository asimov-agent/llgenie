# The claim protocol's run-liveness reader is ONE place (issue #799)

`scripts/bot_claims.py` documents the claim protocol (issues #261/#263/#279/#285): a bot about to
work a subject posts a machine-readable `bot-claim:` marker, and other bots stand down while that
claim holds. The one rule that keeps a dead run from holding a subject for a whole TTL (#291) is
"is the run that posted this claim still alive" — and that question was being re-implemented by
every bot leg:

- `run_is_live()` had **5 definitions** (the owner in `bot_claims.py:137`, plus four legs:
  `issue_implementer.py`, `issue_refiner.py`, `rebase_bot_sweep.py` byte-identical to each other,
  and `fix_bot_sweep.py` with a fifth, differently-shaped copy);
- the `--json "status,conclusion"` read was cached **4 separate ways** (`_LIVE` per leg), so two
  legs in one run could disagree about the same run;
- the general `_gh` seam is issue #797's; **this change claims only the claim-path half**.

The fix consolidates the claim path to ONE reader:

- `scripts/bot_claims.py` now owns the default transport `_gh` (promoted from the byte-identical
  copies the legs kept) and ONE per-process `_LIVE` cache inside `bot_claims.run_is_live(run_id,
  gh_call=...)`. The injectable form stays for tests (a fake `gh` on PATH); production uses the one
  transport so a leg can no longer drift a copy.
- The four legs no longer define `run_is_live`/`_LIVE` — they call
  `bot_claims.run_is_live(...)` through their own `gh` injection. `fix_bot_sweep.occupied` stays a
  thin PR-shaped wrapper over `bot_claims.occupied`.
- A new guard `scripts/claim_reader_guard.py` + `make check-claim-reader` (wired into `ci-unit`,
  classified beside `check-module-names`) refuses a live file that re-opens the run-liveness read
  (`--json "status,conclusion"` with no `--repo`) outside `bot_claims.py`, so the drift cannot
  return.
- `tests/test_bot_claims.py` proves one-cache-per-process (two readers, one `gh` call), and
  `tests/test_claim_reader_guard.py` pins the guard's discriminator and the real-tree-clean
  contract.

The guard's pattern is exact on purpose: a repo-scoped CI reader (`--repo`, `jobs`,
`databaseId,status,conclusion,...`) is a different animal and is NOT the claim path, so only the
claim read — `gh run view <id> --json status,conclusion`, nothing else — is what only
`bot_claims.py` may open.

Delivered as PR #1620 on branch `fix/799-claim-reader-dedup` (base `origin/main@b3df15aa`), ready
for the #1088 owner gate.
