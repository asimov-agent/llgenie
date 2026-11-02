# 2026-11-02 — issue #1090: check-agent-profiles scopes to a lane and ratchets the fleet tree

## What was wrong

`make check-agent-profiles` runs `scripts/check_agent_profiles.py check` — a fleet-wide report whose
**exit code is shared by every lane** (issue #791). The unit tests drive the same `findings()` /
`main([…])`, and the clean-tree ones assert the GLOBAL verdict — `findings(REPO) == []` etc. On this
host, three lanes' live profiles drifted within an hour of their PRs parking, so a lane whose own
profile was correct went red purely because of ANOTHER lane's live edit. The lane must not touch the
other lane's live file, so the only escape was editing the assertion — which is exactly the drift
mechanism #791 prevents.

Measured on `main@a7847c6f` with the real `~/.hermes/profiles`:

```
$ make test-unit  (tests/test_agent_profiles.py, real host)
7 failed: test_committed_tree_passes_the_gate, … all clean-tree tests reading live `~/.hermes`
```

Every one passed the moment `HERMES_PROFILES_HOME` pointed at an empty dir — `138 passed`. The seven
failures were other lanes' live drift leaking into a lane's own tree-only test.

## What the change is

- **`--profile <name>`** (`scripts/check_agent_profiles.py`): filters `findings()` to a lane's own
  paths plus the manifest/fleet findings every lane shares. `_profile_of(where)` reads the first path
  segment (after an optional `agents/`), so a finding about `sibling/…` is dropped from `someone`'s
  scope while `agents/manifest.json` (breakage every lane must still see) is kept. An unknown `name`
  exits 2, mirroring the `--only` contract (#1087): a broken invocation is never a silent pass.
- **`--ratchet`** + **`--update-baseline`**: the committed tree's findings are ratcheted against
  `tests/fixtures/agent-profiles-baseline.json` (set-shaped, import-roots #953/#796 style). The diff is
  tree-only — `live_root()` is isolated inside `tree_findings_sites()` — so a drifted host cannot move
  the bar: a clean lane always greens, while a NEW committed-tree finding still reds the fleet. Re-run
  with `--update-baseline` only to deliberately carry a finding the owner has decided the fleet keeps.
- **`Makefile`**: `check-agent-profiles-ratchet` wired into the CI gate list beside
  `check-import-roots`.
- **`tests/test_agent_profiles.py`**: the seven clean-tree tests isolate `HERMES_PROFILES_HOME` to an
  empty fixture path, so they exercise their tree-only intent instead of a drifted host's accident. Five
  new tests assert the acceptance: scoped `⊆` global (subset is structural, never weaker); a clean lane
  greens under `--profile` despite a drifted sibling; unknown profile exits 2; all seven committed lanes
  pass `--profile <own>`; and the ratchet refuses a new committed-tree finding (re-recording greens).

## Decisions

- **Keep the global check loud.** `--profile` is a zero-cost view for a lane's own PR; nothing about the
  committed-tree or live findings the gate already emits is weakened. The ratchet is what prevents the
  scoped view from becoming an amnesty.
- **The subset guarantee is structural, not tested-by-copy.** `_profile_scope` IS the global list
  filtered to `(None, name)`, so `scoped ⊆ global` cannot drift — the test asserts it, but the code
  cannot violate it.
- **The ratchet reads the tree without live state.** Live drift is host-specific; a finding-count
  baseline that moved with the host would red clean PRs randomly. Tree-only makes the baseline
  byte-identical on every host and in CI.
- **Test isolation, not weaker assertions.** The seven tests still assert the same clean verdict; they
  now judge their own fixture's tree, which is what they always meant.

## Proof

Measured in this worktree on `main@a7847c6f`:

- `make test-unit` (or `pytest tests/test_agent_profiles.py`) → **143 passed** on the REAL drifted host,
  up from 138 because five acceptance tests joined the sixty-eight live tests;
- `scripts/check_agent_profiles.py check --profile llgenie-issse-implementer` on the real host reports
  only my lane's findings (`live-edited-not-tree: …/SOUL.md`, my own `absent-from-tree` skills) and none
  of the planner/security/documentation lanes' 186 global findings — the global check still reports them;
- negative control: on a scratch tree, injecting a `standing-rule` finding the baseline did not carry →
  `--ratchet` exits 1 naming the site; `update_baseline` → exits 0 (ratchet control, proven).

Issue: #1090
