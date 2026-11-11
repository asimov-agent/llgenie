# Gate red triage (llgenie CI)

Three validated triage recipes for a red CI job on a lane branch.

## The run is `failure` but every guard is green except one — read the per-step list

A run `conclusion` is a verdict, not a cause: one failing step fails the whole job,
so "run failure" cannot tell you whether your diff is wrong or a reviewer-owned gate
is red. Read the guard job's **per-step** conclusions at the exact head rather than
the run conclusion:

```sh
gh api repos/<owner>/<repo>/actions/jobs/<job-id> --jq '.steps[]|{name,conclusion}'
```

A common, expected result is every identity/author/closing/base/agents-line/sync-line/
openspec step `success` and **only** `check-pr-acceptance` `failure`. That single red
with all other guards green is the **by-design acceptance self-red**: the linked
issue's own acceptance boxes are still `- [ ]`, which is the reviewer's write-back
step — not a defect in your branch. Fixing "your" code cannot clear it.

- **Never self-tick the linked issue's acceptance criteria to clear this red.**
  Ticking `- [ ]`→`- [x]` on someone else's issue is exactly the fabrication the
  write-back gate exists to prevent; it turns a legitimate "awaiting review" into a
  false "proven".
- State the red precisely: name the step and its `acceptance-unchecked` findings, note
  the linked issue is open with unticked criteria (reviewer-gated), and stop. That is
  the honest, reviewable stop state — not a blocked-on-you failure.
- To confirm it really is the by-design red (and not a genuine criterion your change
  fails to satisfy), run the gate module against the linked issue's real AC text in the
  pinned image and assert both sides — see the probe recipe below.

## `ci-verdict` red while every real job is green — the judge may be counting itself

`ci-verdict` is not a CI job: it is a separate `workflow_run` workflow that reads the finished
CI run and posts a check-run back onto the PR. When that check-run is attributed into the same
run's job list, the verdict's own row appears as an extra job inside the run it judges. A
`ci_scope.verify()` that treats every observed job missing from the decision artifact as a
failure then reds **itself**, forever: run `conclusion: success`, every real job `success`,
`ci-verdict` red, and any number of re-runs reproduce the same text.

The tell, in order:

- The red output lists a row named exactly the verdict's own check name (`ci_verdict.CHECK_NAME`)
  as `FAILED`, and that name appears nowhere in `.github/workflows/ci.yml`'s job list.
- A check-run id that resolves to `.../actions/runs/<id>` (a *workflow run*) rather than
  `.../actions/jobs/<id>` is the judge's own post, not a CI job — that mismatch is the confusion
  that eats a whole turn.
- Run id in the red text is the CI run, but its `attempt` may be older than the last re-run; always
  re-read `attempt,conclusion,headSha` before acting on the verdict.

Prove it against ground truth instead of re-running: download the run's decision artifact, list
the jobs it names, and diff that set against the run's observed job list. Then replay the judge
locally with the real jobs + decision files (`python scripts/ci_verdict.py` with the two file
paths): the unfixed module prints `ci-verdict FAILED` from an empty job row, and the fixed one
prints `verdict=green` on 10 success / 0 failure. One replay is the whole diagnosis.

Remedy is a code fix in the judge, never a re-run: filter observed jobs whose name equals
`CHECK_NAME` out of the job list before calling `verify()`, and add a regression test whose jobs
fixture *includes* a `ci-verdict` row so the self-exclusion is pinned. Because the judge is
main's code, the fix helps the PR only after it merges **and** a run starts from the post-fix
tree — see `gate-run-discipline.md` ("Re-run vs new run").

## Proving a gate RED and GREEN on the real issue text (pinned container)

Before claiming a guard behaves correctly for a fixture, prove it against the actual
expected text with the gate's own function under the repo's pinned image — not a
hand-written mock, which reimplements the old shape and passes a shard the real gate
would fail:

```sh
# write a probe importing the real gate, e.g. scripts/check_pr_acceptance
#   premature-close (criteria unticked)  -> expect ['acceptance-unchecked']  (RED)
#   final-lane close (criteria ticked)   -> expect []                        (GREEN)
docker run --rm -u root --network host \
  -v /var/run/docker.sock:/var/run/docker.sock -v "$PWD":"$PWD":rw -w "$PWD" \
  -e HOME=/tmp llgenie/test:latest python <probe>.py
```

One run asserting both directions is the strongest CI-independent evidence that the
fixture pins the defect and does not just codify current behaviour. Paste the two
verdicts into the issue/PR comment as the reviewer-tickable proof.

## A single-commit branch reds `check-pr-base` after `main` advances

The `linux / unit` job runs a `check-pr-base` step that requires the branch to be cut
from **current** `origin/main`. When `main` advances after you branched, a clean
single-commit branch still reds that step even though your change is unrelated — the
branch's merge-base is now one commit behind the new tip.

- Confirm the trigger: the failing step is `check-pr-base` **and**
  `gh pr view <n> --json mergeable` reads `MERGEABLE` (not `CONFLICTING`).
- Remedy: `git fetch origin main` (explicit refspec `+refs/heads/main:refs/remotes/origin/main`),
  `git rebase origin/main`, re-run the file's tests, then
  `git push --force-with-lease` (plain lease after the fresh fetch — the rebase made the remote tip a non-ancestor). A fresh CI run starts on the new head.
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
