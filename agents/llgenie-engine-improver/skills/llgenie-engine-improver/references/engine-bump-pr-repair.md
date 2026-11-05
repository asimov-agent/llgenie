# Repairing a red engine-bump PR (guards + change-note + unit leg)

An engine-bump PR (the weekly rolling pin) can go red on one of three independent gates. Diagnose
which one before editing anything — they have different fixes and a fix for one does not touch the
others. Read the guard job's failing step, not the PR's red badge.

## The three gates

- **check-pr-closing** — the "no dangling claim" rule. A *claim* is either an `Issue: #N` line in the
  commit/PR text OR a subject/title ending in `(#N)`. Any claim must be re-served by an adjacent
  `closes|fixes|resolves #N` in BOTH the squash commit text and the PR body. The current engine-bump
  convention is "weekly rolling pin; closes no issue" — no claim at all, so no `closes` line is owed.
  Red here means the commit message or body still carries an `Issue: #N` claim (e.g. a stale template
  line) with no adjacent `closes`. Fix: remove the claim from the commit message (amend or re-roll)
  and align the PR body to the convention. Run `make check-pr-closing` locally to prove it before push.
- **check-pr-base** — the branch must be cut from the current `origin/main`. Red means the base pin is
  stale; `git rebase --onto origin/main <merge-base> <branch>` (or re-cut) fixes it.
- **check-docs** (change-note, behavioural-surface rule) — a bump that touches a behavioural surface
  (e.g. `containers/`, `Dockerfile.*`) must ADD an `agent-wiki/<stem>.md` change note wired into
  *this branch's diff*, plus a `docs/changes.d/<pin-fragment>` entry and a `CHANGES.md` row.
  **A note left unchanged from a previous bump does NOT satisfy it** — check-docs diffs
  `merge-base...HEAD`, so a stale note (still pointing at the prior PR/pin) is invisible to the gate.
  Fix: re-point the note to THIS PR and the NEW pin, update the fragment's `old -> new` pin and PR
  ref, then `make changes-index` to regenerate `CHANGES.md`, and **commit** all three together
  (check-docs reads committed HEAD, not the index — staging alone leaves it red).

## The generator force-re-rolls the branch mid-work — apply fixes ADDITIVELY

The engine-bump generator can force-update the branch to a NEWER pin while you are working,
overwriting your push. Evidence: the remote head sha changes and the commit message is the
convention wording at a newer pin than your own edit.

- After every push to an engine-bump branch, re-read the remote tip
  (`git ls-remote <remote> refs/heads/<branch>`) before assuming your edit is the head.
- If re-rolled: read the fresh head, adapt your fix to the NEW pin, and commit it **additively on top**
  of the generator's commit (a fast-forward follow-up). Never amend or overwrite the generator's
  commit — it owns the pin message; your docs/guard fix is a separate additive commit.

## Verify the unit leg in the hermetic container, not on the host

The host's python `pytest` fails on repo tests with **empty stdout and rc 2**, even on a plain
collection — the suite is hermetic and `make test-unit` runs it inside a container
(`$(RUNTIME) run $(TEST_OPTS) $(TEST_IMG)`, image `llgenie/test:latest`, `-v "$(ROOT)":/repo:rw -w
/repo -e HOME=/root`). Trivial throwaway tests pass on the host; the repo's `tests/conftest.py` needs
the container env. So do not chase a host pytest failure as a code bug — it is the wrong runner.

Run a targeted test the same way CI does:

```
docker run --rm -u root -v "$PWD":/repo:rw -w /repo -e HOME=/root \
  llgenie/test:latest python -m pytest tests/<file>::<test> -q --no-header -p no:cacheprovider
```

A `2 passed in 1.1s` inside that container at your pushed head is the real verification the two
assertions the gate reds on now hold — cite it instead of a claim that "CI should pass".

## Ordering that avoids rework

1. Confirm the actual red gate from the guard job's step list.
2. Cut a worktree from the CURRENT `origin/main` (fetched now), not a remembered sha.
3. Fix the specific gate; if a stale pin/base is also involved, rebase first so the guard reads the
   right commit set.
4. Verify each gate locally BEFORE pushing: `make check-pr-closing`, `make check-pr-base` (or a
   `merge-base` check), `make check-docs`; plus the targeted unit tests inside the container.
5. Push, then re-read the remote tip to catch a generator re-roll; apply additively if it happened.
6. Wait for the full CI at the final head and report the green run id + head sha, not a promise.
