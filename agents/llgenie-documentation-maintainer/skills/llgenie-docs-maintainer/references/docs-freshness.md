# Docs freshness — the lane owns README + docs against the tree

Versioned via #1239 (owner directive, 2026-10-31). Applies to the documentation-maintainer lane.

## Remit

The lane owns README.md, `docs/` and every user-facing doc/manpage make target. Whenever a
code/scripts/workflow change lands on `main`, the doc that describes it is re-checked and updated in
the SAME pass as the change, never later. The `make check-docs` gate (Makefile:987) enforces that
every user-facing target is documented — it is the lane's gate, kept green on `main`.

## 30-minute change monitor

On a recurring ~30-min cadence the lane reads `main` for new commits/merges and, before filing or
taking up any other work, answers: **"does any user-facing doc/README need an update for this
merge?"** A merge that is already doc-current (check-docs green at its head, description accurate)
is answered "no gap" and recorded; a merge with a documented-but-description-lagged change is fixed
in the same pass (rebase the doc PR onto the merge, update the description, re-run the gate). Measured
freshness, not passive: a census of what was checked and at which sha is the unit of work.

Checklist, per merge:
1. `git log origin/main -1` — what merged, which heads touched scripts/`.py`/workflows/`.yml`/Makefile.
2. Does any user-facing doc name that target / script / behaviour? (`grep -R <target> README.md docs/`)
3. Is the description still truthful at the new head? (`make check-docs` exit 0; re-read the sentence)
4. Gap → fix the doc in the same pass; no gap → record "checked <sha>, no gap" and move on.

## Never a private profile edit

Any refinement to HOW this lane does documentation (a new checklist, a new gate, a new cadence) is
versioned under `agents/llgenie-documentation-maintainer/` via an issue + PR (issue #791 pattern).
Live is authoritative for drift; a change authored in the tree is mirrored tree→live so
`make sync-agent-profile CHECK=1` stays green. This reference itself is such a versioned refinement.
