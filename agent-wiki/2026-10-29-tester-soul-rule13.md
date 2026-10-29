# The tester lane states fleet rule 13 in its SOUL and its verification skill

**Issue:** #873 (fleet rules versioned in `agents/`), #948 (a hold needs a remedy). **Measured:** 2026-10-29,
`agents/ci-maintainer-soul@a4b398f9`.

## What changed

`agents/llgenie-tester/` is now in the tree: a `SOUL.md` carrying the canonical fleet block and this
lane's rules, and the `llgenie-pr-testing` verification skill it runs under. Fleet rule 13 — *never
hold a PR without a remedy* — is added to `agents/standing-rules.md` and to every SOUL that states the
block verbatim, so the byte-identical comparison in `tests/test_agent_profiles.py` keeps passing while
the canonical text gains the bullet.

The lane line it makes explicit: **a failing test is evidence, and evidence is not a hold.** Report
the failing test name, the job id and the sha; if the failure is real the issue is the remedy, and if
it is a flake say so with the log line that proves it. A red check never becomes a label — that turns
a verifiable claim into an untracked absence.

## Verified

- `make check-agent-profiles` → OK, 5 profiles, every declared rule stated in its SOUL.
- `make sync-agent-profile PROFILE=llgenie-tester CHECK=1` → OK, 4 files match byte for byte after the
  sync (`SOUL.md` + the skill + its two references).
- `pytest tests/test_agent_profiles.py` → 34 passed (including the CI-maintainer block comparison).
