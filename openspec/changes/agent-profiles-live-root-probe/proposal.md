# Change: agent-profiles-live-root-probe

## Why

Issue #923 fixed the lie-by-`.parent` (a base must hold a `<name>/SOUL.md` before being taken as a
profiles home) — but the probe that decides this can itself crash the gate. Measured on `main`
`4f3fc1ef2`:

```
$ HERMES_PROFILE_HOME=/nonexistent-home python3 scripts/check_agent_profiles.py
[check-agent-profiles] FAIL: the gate aborted before finishing
(PermissionError: [Errno 13] Permission denied: '/boot/SOUL.md') — NOTHING was checked (issue #1134)
EXIT=2
```

`Path('/nonexistent-home').parent` is `/`; the probe walks `/`, and an unreadable system directory
(`/boot`, mode 700) raises where the probe should only answer "this is not a profiles directory".
The skip path #919/#923 built — audible caveat, tree checks continue — is unreachable for exactly
the typo class the issue names, and AC1/AC4 of #923 stay unproven: the gate neither skips with the
caveat nor names the rejected base; it aborts and checks NOTHING.

## What Changes

- `live_root_info()`'s shape probe becomes unreadable-tolerant: a candidate directory that cannot
  be read (or whose `SOUL.md` cannot be statted) is *not a profile*, the scan continues; a base
  that cannot be listed at all resolves to "no live comparison" — the skip path, never an abort.
- When a **provided** variable resolves to a rejected base, the skip line names the resolved base
  path (AC4), so a reader sees which directory was rejected and why.
- Tests plant the unreadable shapes in fixtures (mode-000 candidate inside a real profiles home;
  an unlistable base) so the class is pinned, plus the host probe (`/nonexistent-home` → exit 0 +
  caveat) as the replayable AC proof.

## Impact

- `scripts/check_agent_profiles.py` — probe + skip-line source text only; finding semantics unchanged.
- `tests/test_agent_profiles.py` — new cases; existing skip/parent tests must stay green.
- No workflow, no CI-stage wiring change (the gate target already exists and runs in `ci-unit`).
