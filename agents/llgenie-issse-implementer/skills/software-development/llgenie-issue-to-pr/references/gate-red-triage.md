# Gate red triage (llgenie CI)

Two validated triage recipes for a red CI job on a lane branch.

## A single-commit branch reds `check-pr-base` after `main` advances

The `linux / unit` job runs a `check-pr-base` step that requires the branch to be cut
from **current** `origin/main`. When `main` advances after you branched, a clean
single-commit branch still reds that step even though your change is unrelated — the
branch's merge-base is now one commit behind the new tip.

- Confirm the trigger: the failing step is `check-pr-base` **and**
  `gh pr view <n> --json mergeable` reads `MERGEABLE` (not `CONFLICTING`).
- Remedy: `git fetch origin main` (explicit refspec `+refs/heads/main:refs/remotes/origin/main`),
  `git rebase origin/main`, re-run the file's tests, then
  `git push --force-with-lease --force-if-includes`. A fresh CI run starts on the new head.
- Do **not** merely re-run the red job — it fails again on the same stale base. The rebase
  is warranted here precisely because the gate itself fails, which is the exception to
  "rebase only when CONFLICTING".

## A gate's test suite reds on your host but CI is green — ambient live-state drift

Gate tests (profile checks, sync guards, marker scanners) sometimes read **real machine
state** by default — e.g. `~/.hermes/profiles` via `HERMES_PROFILES_HOME`, a live checkout.
On a host where that state has drifted (other lanes' live edits, uncommitted local files),
those tests red even when your change is innocent: they compare a clean fixture tree
against the drifted live home and report the *host's* findings as failures.

- Prove it before designing any fix: re-run the suite with the state env var pointed at an
  empty / nonexistent directory, e.g.
  `HERMES_PROFILES_HOME=/tmp/nonexistent-profiles-home pytest tests/<file> -q`.
  If every test passes, the reds are ambient drift, not your regression.
- Only then decide scope. If the issue is "one lane's live drift reds every lane's PR", the
  fix is to scope the check to a lane (a `--profile <lane>` filter that returns a strict
  subset of the global findings, plus a repo-wide finding-count ratchet baseline, and
  isolating the live home in the red tests) — **not** editing other lanes' live files, which
  is out of bounds for this lane.
- Never attribute a host-only red to your diff without this isolation check: CI (which has
  no live home and no drifted checkout) is the discriminator between "your bug" and
  "the machine's state".
