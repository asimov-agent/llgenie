# Post-merge verification — prove what MERGED holds ON `main`

When asked to audit "what merged tonight actually holds on main", every criterion is measured at the
default-branch tip, NOT at the PR head that was green before merge. Read the tip fresh
(`git fetch origin main; git rev-parse origin/main`), classify each item by its own gate, and never
use a queued / in-progress CI run as corroboration — settle it with a host command. A live job with
`completed_at=null` is a SNAPSHOT, not a verdict: quote it as corroboration-at-most, and answer the
item with your own measurement.

## Census / "measured at" refresh (`docs/ARCHITECTURE.md`)

- **Exactly ONE pointer line.** `grep -cE 'measured at `[0-9a-f]+`' docs/ARCHITECTURE.md` == 1 — a
  second "measured at" that is prose (a gate-description row) is a false hit, read it before counting.
- **The pointer is an ancestor of the tip.** `git merge-base --is-ancestor <pointer> origin/main`.
- **Run the gate on the host at the tip.** `python3 scripts/check_architecture_census.py check` → rc=0.
- **Reconcile the claimed count by MEASUREMENT, at the pointer — not at HEAD.** The doc says "N
  tracked files"; `git ls-tree -r --name-only <pointer> | wc -l` must equal N, AND every per-dir
  count in the doc's row must equal `git ls-tree -r --name-only <pointer> | grep -c '^<dir>/'`. A doc
  that "counts at `<sha>`" is verified by counting AT that sha; a count at HEAD is a different tree and
  proves nothing about the claim. This is the reconciliation test that turns "2009 tracked" from an
  assertion into a measurement.

## A gate-behaviour fix — negative controls, in a THROWAWAY clone

"The gate was fixed" is proved by the gate REJECTING what it claims to reject, not by one happy-path
`rc=0`. Build a throwaway copy so you never mutate the real tree:

```
S=$SCRATCH; rm -rf $S/x; git clone -q --shared <repo> $S/x && cd $S/x && git checkout -q <tip-sha>
```

`--shared` is fast (the clone references the source objects). Run every mutation inside the clone and
`git reset --hard <tip-sha>` between controls — the real repo is never touched. For the architecture
census gate the four controls, each run bare (`cmd >log 2>&1; echo rc=$?`; NEVER pipe — `| tail`
reports the filter's `$?`, so a genuine `rc=1` prints `rc=0`):

| control | setup | expected |
|---|---|---|
| C1 file-add, block untouched | commit a new file, leave the census block | **rc=0** — the whole point: a file-adding branch needs no pointer edit |
| C2 real, non-ancestor pointer | commit on a side branch off an EARLY commit; point the doc at that sha | **rc=1**, and it NAMES the sha + says "not an ancestor of HEAD" |
| C3 numbers disagree | change the claimed total (2009→2010) | **rc=1**, names both values, "1 claim(s) stale" |
| C4 pointer removed | delete the `(measured at …)` clause | **rc=1**, names `docs/ARCHITECTURE.md`, "no usable referent" |

C2 is the one that matters most: seed a non-ancestor commit by `git checkout <old-commit>; commit a
probe file` (a child of an ancestor is not itself an ancestor), then point the doc at it. If the gate
names the sha and calls it non-ancestor, it rejects the thing the fix claims to reject.

## A test-routing change — "routed", not "skipped"

"Four real-call tests out of ci-unit" is only true if they RUN somewhere else. A test that is merely
`skip`ped (or excluded and never run) is the dodge the PR claimed to fix. Check all three legs:

1. **Marked:** each test carries the marker — `grep -B3 -E 'def <test_name>' <file> | grep -c
   'mark.network'` == 1.
2. **Excluded from the hermetic gate:** the unit selection drops it — `scripts/unit_tests.py`'s default
   marker expression is `-m "not network"` (the code comment states the seam; `make test-unit` uses
   the default), so a `network`-marked test cannot enter ci-unit.
3. **RUN by the other pipeline:** the live pipeline selects it — `scripts/unit_tests.py run --marker
   network` (`make test-unit-network`), wired into the real-Hub workflow on push-to-main / nightly /
   dispatch, and NEVER as a PR check.

Marker present + excluded from ci-unit + executed in the live pipeline = ROUTED. Marker present but
only excluded = silently skipped. Say which, with the file and the seam line, not just "removed".

## Trust the tip you re-read, not a watcher you armed earlier

A background watcher (a `gh run watch` / poll loop) is pinned to a run/sha at the moment you start it.
If the default branch moves while it runs (§5: heads move), the run it is polling becomes a
SUPERSEDED tip and its eventual "verdict" describes a tree that is no longer the default branch. When
that happens, stop the stale watcher (`kill <pid>`) rather than let it fire a superseded result, and
re-point to the current tip's run if corroboration is still wanted. The independent host measurement
is what settles the item; the watcher is corroboration only.
