# tasks — sync-blocked-line-2097

## 1. Shared measurement

- [x] 1.1 `scripts/agent_profile_sync.py` exposes `truncation_report(agents, name, dest)` — a quiet
      measurement (files, differ, shrink, first path, byte counts, reason string) using the same
      criterion `check()` refuses on; returns None when the live home does not exist.

## 2. Gate: honest blocked line

- [x] 2.1 `scripts/check_pr_hygiene.py`: parse `SYNC-BLOCKED: <p> #<issue> <measured reason>`;
      honor it per profile with the measured/fabrication/unmeasurable rules of the spec; keep the
      exact `SYNC:` line and the no-line finding unchanged; register the
      `check_pr_hygiene -> agent_profile_sync` edge in `scripts/package-layers.json`.
- [x] 2.2 `tests/test_pr_hygiene_sync_line.py`: blocked-line-passes (measured home), no-line-fails,
      exact-SYNC-passes, fabrication-reds, unmeasurable-home-accepts; CLI rc proof.

## 3. Preflight: emits the measured line

- [x] 3.1 `scripts/bot_preflight.py` + `mk/bots.mk` (ISSUE=): print the paste-ready
      `SYNC-BLOCKED:` line for truncated tree copies, keep the `SYNC:` guidance otherwise, refuse a
      fabricated blocked line in `BODY=`; test in `tests/test_bot_preflight.py`.

## 4. Prove it green

- [x] 4.1 Targeted pytest green; `make check-pr-sync-line` fixture proof for
      `SYNC-BLOCKED: llgenie-planner ...` at the landing head; host proof `make bot-preflight` on a
      scratch tree touching a genuinely truncated profile; `make lane-preflight` + `make test-unit`
      green; docs trio + openspec validate green.
